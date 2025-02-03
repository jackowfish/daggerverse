"""Thunder Compute module for running GPU workloads"""
import time
from typing import Annotated

import dagger
from dagger import Doc, dag, function, object_type


@object_type
class Thunder:
    """Thunder provides integration with Thunder Compute for GPU workloads"""

    def __init__(self):
        self._container = None
        self._base_url = "dagger.jackdecker.org"

    @function
    def with_token(self, token: Annotated[dagger.Secret, Doc("Thunder API token")]) -> "Thunder":
        """Configure the Thunder API token"""
        if self._container is None:
            self._container = (
                dag.container()
                .from_("alpine:latest")
                .with_secret_variable("TNR_API_TOKEN", token)
                .with_exec(["apk", "add", "curl", "jq"])
                .with_env_variable("CACHE_BUSTED_AT", str(time.time()))
            )
        return self

    @function
    def with_base_url(
        self, url: Annotated[str, Doc("Base URL for Thunder API")]
    ) -> "Thunder":
        """Configure a custom base URL"""
        self._base_url = url
        return self

    @function
    async def create_pod(self) -> str:
        """Create a new Thunder compute pod and return its instance ID"""
        if self._container is None:
            raise RuntimeError("token not set, call with_token first")

        api_url = f"https://{self._base_url}/api"
        
        result = await (
            self._container
            .with_exec([
                "sh", "-c",
                f"curl -s -X POST '{api_url}/pods' "
                f"-H 'Authorization: Bearer $TNR_API_TOKEN' "
                f"-H 'Content-Type: application/json' "
                f"-d '{{}}' | jq -r '.instance_id'"
            ])
            .stdout()
        )
        return result.strip()

    @function
    async def wait_for_pod(self, instance_id: str) -> None:
        """Wait for a pod to be ready"""
        if self._container is None:
            raise RuntimeError("token not set, call with_token first")

        api_url = f"https://{self._base_url}/api"
        
        await (
            self._container
            .with_exec([
                "sh", "-c",
                f"while true; do "
                f"status=$(curl -s -H 'Authorization: Bearer $TNR_API_TOKEN' "
                f"'{api_url}/pods/{instance_id}' | jq -r '.status'); "
                f"if [ \"$status\" = \"running\" ]; then break; fi; "
                f"sleep 5; done"
            ])
            .sync()
        )

    @function
    async def get_pod_host(self, instance_id: str) -> str:
        """Get the host URL for a pod"""
        if self._container is None:
            raise RuntimeError("token not set, call with_token first")

        api_url = f"https://{self._base_url}/api"
        
        result = await (
            self._container
            .with_exec([
                "sh", "-c",
                f"curl -s -H 'Authorization: Bearer $TNR_API_TOKEN' "
                f"'{api_url}/pods/{instance_id}' | jq -r '.host'"
            ])
            .stdout()
        )
        return result.strip()

    @function
    async def deploy(self) -> str:
        """Deploy a new Thunder compute instance with a Dagger runner
        
        Returns the command to set the DAGGER_RUNNER_HOST environment variable
        """
        # Create pod and get instance ID
        instance_id = await self.create_pod()

        # Wait for pod to be ready
        await self.wait_for_pod(instance_id)

        # Get host URL
        host = await self.get_pod_host(instance_id)

        # Return the environment variable command
        return f"export _EXPERIMENTAL_DAGGER_RUNNER_HOST={host}"

    @function
    async def destroy(
        self, instance_id: Annotated[str, Doc("Instance ID to destroy")]
    ) -> None:
        """Destroy a Thunder compute instance"""
        if self._container is None:
            raise RuntimeError("token not set, call with_token first")

        api_url = f"https://{self._base_url}/api"
        
        await (
            self._container
            .with_exec([
                "sh", "-c",
                f"curl -s -X DELETE '{api_url}/pods/{instance_id}' "
                f"-H 'Authorization: Bearer $TNR_API_TOKEN'"
            ])
            .sync()
        )