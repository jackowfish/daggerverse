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
    async def deploy(self, token: Annotated[str, Doc("Thunder API token")]) -> str:
        """Deploy a new Thunder compute instance with a Dagger runner"""
        if not token:
            raise ValueError("Token is required")

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
                    f"curl -s -X POST '{THUNDER_API_ENDPOINT}/pods' "
                    f"-H 'Authorization: Bearer {token}' "
                ])
                .stdout()
            )

            # Parse the JSON response
            response_data = json.loads(raw_response)
            instance_id = response_data['instance_id']
            private_key = response_data['private_key']
            host = response_data['host']

            if not instance_id:
                raise RuntimeError(f"Failed to get instance_id from API response: {raw_response}")

            # Wait for pod to be ready
            max_retries = 30
            retry_count = 0
            while retry_count < max_retries:
                status_response = await (
                    container
                    .with_env_variable("CACHEBUSTER", str(time()))
                    .with_exec([
                        "sh", "-c",
                        f"curl -s '{THUNDER_API_ENDPOINT}/pods/{instance_id.strip()}' "
                        f"-H 'Authorization: Bearer {token}'"
                    ])
                    .stdout()
                )

                # Parse status response
                status_data = json.loads(status_response)
                print(status_data)
                status = status_data.get('status', '')

                if status == "running":
                    # Return both the environment variable and key information
                    thunder_dir = os.path.join("~", ".thunder")
                    keys_dir = os.path.join(thunder_dir, "keys")
                    key_path = os.path.join(keys_dir, f"{instance_id}")
                    
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
                    # Append to SSH config instead of overwriting
                    f'''cat >> ~/.ssh/config << 'EOF'
\nHost {host.split('@')[1].split(':')[0]}
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    IdentityFile {key_path}

EOF''',  # Note: the EOF needs to be at the start of the line
                    'chmod 600 ~/.ssh/config',
                    f'''echo -e "export _EXPERIMENTAL_DAGGER_RUNNER_HOST="{host}:22""'''
                ]
                    
                    return "\n".join(setup_instructions)

                retry_count += 1
                if retry_count < max_retries:
                    await (
                        container
                        .with_exec(["sleep", "3"])
                        .sync()
                    )

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
                host = host.split('@')[1].split(':')[0]

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
                f'rm -f {key_path}'
            ]

            if host:
                cleanup_instructions.extend([
                    'if [ -f ~/.ssh/config ]; then',
                    '  # Create temp file without the host entry',
                    f'  awk \'/^Host {host}/{{skip=1;next}} /^$/ {{if (skip) {{skip=0;next}} else print}} !skip{{print}}\' ~/.ssh/config > ~/.ssh/config.tmp',
                    '  # Replace original with temp file',
                    '  mv ~/.ssh/config.tmp ~/.ssh/config',
                    'fi'
                ])

            return "\n".join(cleanup_instructions)

        except Exception as e:
            raise RuntimeError(f"Failed to destroy Thunder instance: {str(e)}")