"""Thunder Compute module for running GPU workloads"""
import time
from typing import Annotated

import dagger
from dagger import Doc, dag, function, Module

@dagger.object_type
class Thunder(Module):
    """Thunder provides integration with Thunder Compute for GPU workloads"""

    @function
    async def deploy(self, token: Annotated[str, Doc("Thunder API token")]) -> str:
        """Deploy a new Thunder compute instance with a Dagger runner
        
        Returns the command to set the DAGGER_RUNNER_HOST environment variable
        """
        if not token:
            raise ValueError("Token is required")

        base_url = "api.thundercompute.com"
        api_url = f"https://{base_url}:8443"

        # Create base container with tools and token
        container = (
            dag.container()
            .from_("alpine:latest")
            .with_exec(["apk", "add", "--no-cache", "curl", "jq"])
            .with_env_variable("CACHE_BUSTED_AT", str(time.time()))
            .with_env_variable("TNR_API_TOKEN", token)
        )

        try:
            # Test the token and API first
            test_response = await (
                container
                .with_exec([
                    "sh", "-c",
                    f"curl -k -s '{api_url}' "
                    f"-H 'Authorization: Bearer $TNR_API_TOKEN'"
                ])
                .stdout()
            )
            print(f"API test response: {test_response}")

            # Create pod with more verbose output
            response = await (
                container
                .with_exec([
                    "sh", "-c",
                    f"curl -k -s -X POST '{api_url}/pods' "
                    f"-H \"Authorization: Bearer $TNR_API_TOKEN\" "
                    f"-H 'Content-Type: application/json' "
                    f"-d '{{}}'"
                ])
                .stdout()
            )

            # Now try to get instance ID
            instance_id = await (
                container
                .with_exec([
                    "sh", "-c",
                    f"echo '{response}' | jq -r '.instance_id' 2>/dev/null || echo 'Failed to parse JSON'"
                ])
                .stdout()
            )
            instance_id = instance_id.strip()

            if not instance_id or instance_id == "null" or instance_id == "Failed to parse JSON":
                raise RuntimeError(
                    f"Failed to get instance ID from API response.\n"
                    f"Full response: {response}\n"
                    f"Curl command: curl -k -X POST '{api_url}/pods' -H 'Authorization: Bearer ***' -H 'Content-Type: application/json' -d '{{}}'"
                )

            # Wait for pod to be ready
            await (
                container
                .with_exec([
                    "sh", "-c",
                    f"while true; do "
                    f"status=$(curl -k -s -H 'Authorization: Bearer $TNR_API_TOKEN' "
                    f"'{api_url}/pods/{instance_id}' | jq -r '.status'); "
                    f"if [ \"$status\" = \"running\" ]; then break; fi; "
                    f"echo \"Waiting for pod {instance_id} to be ready (status: $status)...\"; "
                    f"sleep 5; done"
                ])
                .sync()
            )

            # Get host URL and port
            host_info = await (
                container
                .with_exec([
                    "sh", "-c",
                    f"curl -k -s -H 'Authorization: Bearer $TNR_API_TOKEN' "
                    f"'{api_url}/pods/{instance_id}' | jq -r '.host,.port'"
                ])
                .stdout()
            )
            host, port = host_info.strip().split('\n')

            if not host or host == "null" or not port or port == "null":
                raise RuntimeError(f"Failed to get host/port from API response for instance {instance_id}")

            # Return the environment variable command with host:port
            # Note: host already includes 'tcp://' prefix from the API
            return f"export _EXPERIMENTAL_DAGGER_RUNNER_HOST=tcp://{host}:{port}"

        except Exception as e:
            raise RuntimeError(f"Failed to deploy Thunder instance: {str(e)}")

    @function
    async def destroy(
        self,
        token: Annotated[str, Doc("Thunder API token")],
        instance_id: Annotated[str, Doc("Instance ID to destroy")]
    ) -> None:
        """Destroy a Thunder compute instance"""
        if not token:
            raise ValueError("Token is required")
        if not instance_id:
            raise ValueError("Instance ID is required")

        base_url = "dagger.jackdecker.org"
        api_url = f"https://{base_url}"

        try:
            container = (
                dag.container()
                .from_("alpine:latest")
                .with_exec(["apk", "add", "--no-cache", "curl"])
                .with_env_variable("TNR_API_TOKEN", token)
            )

            response = await (
                container
                .with_exec([
                    "sh", "-c",
                    f"echo 'Destroying pod {instance_id}...' && "
                    f"curl -k -s -X DELETE '{api_url}/pods/{instance_id}' "
                    f"-H 'Authorization: Bearer $TNR_API_TOKEN'"
                ])
                .stdout()
            )

            if response.strip():
                raise RuntimeError(f"Unexpected response from API: {response}")

        except Exception as e:
            raise RuntimeError(f"Failed to destroy Thunder instance: {str(e)}")