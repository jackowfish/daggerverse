"""Thunder Compute module for running GPU workloads"""
from typing import Annotated, List, Dict, Any
import json
import os
from time import time
import traceback

import dagger
from dagger import Doc, dag, function, Module

# Get API endpoint from environment variable or use default
DEFAULT_API_ENDPOINT = "https://dagger.thundercompute.com/api"
THUNDER_API_ENDPOINT = os.getenv("THUNDER_API_ENDPOINT", DEFAULT_API_ENDPOINT)

@dagger.object_type
class Thunder(Module):
    """Thunder provides integration with Thunder Compute for GPU workloads"""

    @function
    async def deploy(self, token: Annotated[str, Doc("Thunder API token")], gpu_type: Annotated[str, Doc("GPU type")] = "t4") -> str:
        """Deploy a new Thunder compute instance with a Dagger runner"""
        if gpu_type not in ['t4', 'a100', 'a100xl']:
            gpu_type = 't4'

        container = (
            dag.container()
            .with_env_variable("CACHEBUSTER", str(time()))
            .from_("alpine:latest")
            .with_exec(["apk", "add", "--no-cache", "curl"])
        )

        try:
            # Create pod and store raw response
            raw_response = await (
                container
                .with_env_variable("CACHEBUSTER", str(time()))
                .with_exec([
                    "sh", "-c",
                    f"curl -s -X POST '{THUNDER_API_ENDPOINT}/pods/{gpu_type}/1' "
                    f"-H 'Authorization: Bearer {token}' "
                ])
                .stdout()
            )

            # Parse the JSON response
            response_data = json.loads(raw_response)
            instance_id = response_data.get('instance_id')
            private_key = response_data.get('private_key')
            host = response_data.get('host')
            port = response_data.get('port')

            if not instance_id:
                raise RuntimeError(f"Failed to get instance_id from API response: {raw_response}")
            if not port:
                raise RuntimeError(f"Failed to get port from API response: {raw_response}")

            # Wait for pod to be ready
            max_retries = 30
            retry_count = 0
            
            # Create a container for status checks
            status_container = (
                container
                .with_exec(["apk", "add", "--no-cache", "curl"])
            )
            
            while retry_count < max_retries:
                status_response = await (
                    status_container
                    .with_env_variable("CACHEBUSTER", str(time()))
                    .with_exec([
                        "sh", "-c",
                        f'''sleep {3 if retry_count > 0 else 0} && '''
                        f'''curl -s '{THUNDER_API_ENDPOINT}/pods/{instance_id.strip()}' '''
                        f'''-H 'Authorization: Bearer {token}' '''
                    ])
                    .stdout()
                )

                # Parse status response
                status_data = json.loads(status_response)
                print(f"Attempt {retry_count + 1}/{max_retries}: Status = {status_data.get('status', '')}")
                status = status_data.get('status', '')

                if status == "running":
                    # Return both the environment variable and key information
                    thunder_dir = os.path.join("~", ".thunder")
                    keys_dir = os.path.join(thunder_dir, "keys")
                    key_path = os.path.join(keys_dir, f"{instance_id}")
                    
                    # Wait for SSH to be ready and get host key
                    host_key = await (
                        container
                        .from_("alpine:latest")
                        .with_exec(["apk", "add", "--no-cache", "openssh-client"])
                        .with_env_variable("CACHEBUSTER", str(time()))
                        .with_exec([
                            "sh", "-c",
                            # Retry ssh-keyscan with proper error handling and port
                            f'''for i in $(seq 1 10); do
                                echo "Attempt $i: Scanning host {host} port {port}..."
                                if KEY=$(ssh-keyscan -H -p {port} {host} 2>/dev/null); then
                                    echo "$KEY"
                                    exit 0
                                fi
                                sleep 3
                            done
                            echo "Failed to get host key after 10 attempts"
                            exit 1'''
                        ])
                        .stdout()
                    )
                    
                    # Create instructions for setting up the key
                    setup_instructions = [
                        f'mkdir -p {keys_dir}',
                        f'chmod 700 {thunder_dir} {keys_dir}',
                        f'cat > {key_path} << EOL\n{private_key}\nEOL',
                        f'chmod 600 {key_path}',
                        f'eval $(ssh-agent)',
                        f'ssh-add {key_path}',
                        'mkdir -p ~/.ssh',
                        'chmod 700 ~/.ssh',
                        # Add host key to known_hosts with port
                        f'cat > ~/.ssh/known_hosts.tmp << EOL\n[{host}]:{port} {host_key}\nEOL',
                        'cat ~/.ssh/known_hosts.tmp >> ~/.ssh/known_hosts',
                        'rm ~/.ssh/known_hosts.tmp',
                        'chmod 600 ~/.ssh/known_hosts',
                        # Add SSH config with port
                        f'''cat >> ~/.ssh/config << 'EOF'
\nHost {host}
    User root
    Port {port}
    IdentityFile {key_path}

EOF''',
                        'chmod 600 ~/.ssh/config',
                        f'''echo -e "export _EXPERIMENTAL_DAGGER_RUNNER_HOST="ssh://root@{host}:{port}""'''
                    ]
                    
                    return "\n".join(setup_instructions)

                retry_count += 1

            raise RuntimeError("Timed out waiting for Thunder instance to be ready")

        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Failed to deploy Thunder instance: {str(e)}")

    @function
    async def status(self, token: Annotated[str, Doc("Thunder API token")]) -> str:
        """List all active Thunder compute instances"""
        if not token:
            raise ValueError("Token is required")

        try:
            container = (
                dag.container()
                .from_("alpine:latest")
                .with_exec(["apk", "add", "--no-cache", "curl"])
            )

            # Get pods list
            response = await (
                container
                .with_env_variable("CACHEBUSTER", str(time()))
                .with_exec([
                    "sh", "-c",
                    f"curl -s '{THUNDER_API_ENDPOINT}/pods' "
                    f"-H 'Authorization: Bearer {token}'"
                ])
                .stdout()
            )

            # Parse the JSON response
            response_data = json.loads(response)
            pods_list = response_data.get('pods', [])

            if not pods_list:
                return "No active Thunder instances found"

            result = "Active Thunder instances:\n"
            for pod in pods_list:
                result += f"\nInstance ID: {pod['instance_id']}"
                result += f"\nStatus: {pod['status']}"
                result += f"\nHost: {pod.get('host', 'Not available yet')}"
                result += "\n"

            return result

        except Exception as e:
            raise RuntimeError(f"Failed to list Thunder instances: {str(e)}")

    @function
    async def destroy(
        self,
        token: Annotated[str, Doc("Thunder API token")],
        instance_id: Annotated[str, Doc("Instance ID to destroy")]
    ) -> str:
        """Destroy a Thunder compute instance and clean up associated SSH keys and config"""
        if not token:
            raise ValueError("Token is required")
        if not instance_id:
            raise ValueError("Instance ID is required")

        try:
            container = (
                dag.container()
                .from_("alpine:latest")
                .with_exec(["apk", "add", "--no-cache", "curl"])
            )

            # First get the host information before destroying
            status_response = await (
                container
                .with_env_variable("CACHEBUSTER", str(time()))
                .with_exec([
                    "sh", "-c",
                    f"curl -s '{THUNDER_API_ENDPOINT}/pods/{instance_id}' "
                    f"-H 'Authorization: Bearer {token}'"
                ])
                .stdout()
            )

            # Parse the response to get host info for cleanup
            status_data = json.loads(status_response)
            host = status_data.get('host', '')
            if host:
                host = host

            # Destroy the instance
            await (
                container
                .with_env_variable("CACHEBUSTER", str(time()))
                .with_exec([
                    "sh", "-c",
                    f"curl -s -X DELETE '{THUNDER_API_ENDPOINT}/pods/{instance_id}' "
                    f"-H 'Authorization: Bearer {token}'"
                ])
                .sync()
            )

            # Create cleanup instructions
            thunder_dir = os.path.join("~", ".thunder")
            keys_dir = os.path.join(thunder_dir, "keys")
            key_path = os.path.join(keys_dir, f"{instance_id}")
            
            cleanup_instructions = [
                f'rm -f {key_path}',
                # Remove host from known_hosts if it exists
                f'ssh-keygen -R {host} 2>/dev/null || true',
                # Remove SSH config entry if it exists
                'if [ -f ~/.ssh/config ]; then',
                '  # Create temp file without the host entry',
                f'  awk \'/^Host {host}/{{skip=1;next}} /^$/ {{if (skip) {{skip=0;next}} else print}} !skip{{print}}\' ~/.ssh/config > ~/.ssh/config.tmp',
                '  # Replace original with temp file',
                '  mv ~/.ssh/config.tmp ~/.ssh/config',
                'fi'
            ]

            return "\n".join(cleanup_instructions)

        except Exception as e:
            raise RuntimeError(f"Failed to destroy Thunder instance: {str(e)}")