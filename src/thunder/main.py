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

        base_url = "dagger.thundercompute.com"
        api_url = f"https://{base_url}"

        container = (
            dag.container()
            .from_("alpine:latest")
            .with_exec(["apk", "add", "--no-cache", "curl", "jq"])
        )

        try:
            # Create pod and store raw response
            raw_response = await (
                container
                .with_exec([
                    "curl",
                    "-s",  # silent
                    "-H", f"Authorization: Bearer {token}",
                    "-H", "Content-Type: application/json",
                    "-d", "{}",  # Empty JSON body
                    f"{api_url}/api/pods"
                ])
                .stdout()
            )

            # Check if curl failed
            if raw_response == "CURL_FAILED":
                raise RuntimeError("Failed to make API request")

            # Validate JSON response
            json_valid = await (
                container
                .with_exec([
                    "sh", "-c",
                    f"echo '{raw_response}' | jq . >/dev/null 2>&1 && echo 'VALID' || echo 'INVALID'"
                ])
                .stdout()
            )

            if json_valid.strip() == "INVALID":
                raise RuntimeError(f"Invalid JSON response from API: {raw_response}")

            # Parse instance_id and host
            instance_id = await (
                container
                .with_exec([
                    "sh", "-c",
                    f"echo '{raw_response}' | jq -r '.instance_id // empty'"
                ])
                .stdout()
            )
            host = await (
                container
                .with_exec([
                    "sh", "-c",
                    f"echo '{raw_response}' | jq -r '.host // empty'"
                ])
                .stdout()
            )

            if not host.strip() or not instance_id.strip():
                raise RuntimeError(f"Failed to get host/instance_id from API response: {raw_response}")

            # The host already includes the full TCP URL
            return f'export _EXPERIMENTAL_DAGGER_RUNNER_HOST="{host.strip()}"'

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

        base_url = "dagger.thundercompute.com"
        api_url = f"https://{base_url}"

        try:
            container = (
                dag.container()
                .from_("alpine:latest")
                .with_exec(["apk", "add", "--no-cache", "curl"])
            )

            await (
                container
                .with_exec([
                    "sh", "-c",
                    f"curl -s -X DELETE '{api_url}/api/pods/{instance_id}' "
                    f"-H 'Authorization: Bearer {token}'"
                ])
                .sync()
            )

        except Exception as e:
            raise RuntimeError(f"Failed to destroy Thunder instance: {str(e)}")