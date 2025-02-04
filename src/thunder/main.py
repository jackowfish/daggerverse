"""Thunder Compute module for running GPU workloads"""
from typing import Annotated

import dagger
from dagger import Doc, dag, function, Module

@dagger.object_type
class Thunder(Module):
    """Thunder provides integration with Thunder Compute for GPU workloads"""

    @function
    async def deploy(self, token: Annotated[str, Doc("Thunder API token")]) -> str:
        """Deploy a new Thunder compute instance with a Dagger runner"""
        if not token:
            raise ValueError("Token is required")

        base_url = "api.thundercompute.com"
        api_url = f"https://{base_url}"

        container = (
            dag.container()
            .from_("alpine:latest")
            .with_exec(["apk", "add", "--no-cache", "curl", "jq"])
            .with_env_variable("TNR_API_TOKEN", token)
        )

        try:
            # Create pod
            response = await (
                container
                .with_exec([
                    "sh", "-c",
                    f"curl -k -s -X POST '{api_url}/pod/create' "
                    f"-H 'Authorization: Bearer $TNR_API_TOKEN' "
                    f"-H 'Content-Type: application/json'"
                ])
                .stdout()
            )

            # Parse host and port
            host = await (
                container
                .with_exec([
                    "sh", "-c",
                    f"echo '{response}' | jq -r '.host'"
                ])
                .stdout()
            )
            port = await (
                container
                .with_exec([
                    "sh", "-c",
                    f"echo '{response}' | jq -r '.port'"
                ])
                .stdout()
            )

            if not host.strip() or not port.strip():
                raise RuntimeError(f"Failed to get host/port from API response: {response}")

            return f"export _EXPERIMENTAL_DAGGER_RUNNER_HOST={host.strip()}:{port.strip()}"

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

        base_url = "api.thundercompute.com"
        api_url = f"https://{base_url}"

        try:
            container = (
                dag.container()
                .from_("alpine:latest")
                .with_exec(["apk", "add", "--no-cache", "curl"])
                .with_env_variable("TNR_API_TOKEN", token)
            )

            await (
                container
                .with_exec([
                    "sh", "-c",
                    f"curl -k -s -X DELETE '{api_url}/pod/{instance_id}/delete' "
                    f"-H 'Authorization: Bearer $TNR_API_TOKEN'"
                ])
                .sync()
            )

        except Exception as e:
            raise RuntimeError(f"Failed to destroy Thunder instance: {str(e)}")