"""Thunder Compute module for running GPU workloads"""
import time
from typing import Annotated

import dagger
from dagger import Doc, dag, function, Module


class Thunder(Module):
    """Thunder provides integration with Thunder Compute for GPU workloads"""

    @function
    async def deploy(self, token: Annotated[str, Doc("Thunder API token")]) -> str:
        """Deploy a new Thunder compute instance with a Dagger runner
        
        Returns the command to set the DAGGER_RUNNER_HOST environment variable
        """
        base_url = "dagger.thundercompute.org"
        api_url = f"https://{base_url}/api"

        container = (
            dag.container()
            .from_("alpine:latest")
            .with_secret_variable("TNR_API_TOKEN", dagger.Secret(token))
            .with_exec(["apk", "add", "curl", "jq"])
            .with_env_variable("CACHE_BUSTED_AT", str(time.time()))
        )

        # Create pod and get instance ID
        instance_id = await (
            container
            .with_exec([
                "sh", "-c",
                f"curl -s -X POST '{api_url}/pods' "
                f"-H 'Authorization: Bearer $TNR_API_TOKEN' "
                f"-H 'Content-Type: application/json' "
                f"-d '{{}}' | jq -r '.instance_id'"
            ])
            .stdout()
        )
        instance_id = instance_id.strip()

        # Wait for pod to be ready
        await (
            container
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

        # Get host URL
        host = await (
            container
            .with_exec([
                "sh", "-c",
                f"curl -s -H 'Authorization: Bearer $TNR_API_TOKEN' "
                f"'{api_url}/pods/{instance_id}' | jq -r '.host'"
            ])
            .stdout()
        )

        # Return the environment variable command
        return f"export _EXPERIMENTAL_DAGGER_RUNNER_HOST={host.strip()}"

    @function
    async def destroy(
        self,
        token: Annotated[str, Doc("Thunder API token")],
        instance_id: Annotated[str, Doc("Instance ID to destroy")]
    ) -> None:
        """Destroy a Thunder compute instance"""
        base_url = "dagger.thundercompute.org"
        api_url = f"https://{base_url}/api"

        container = (
            dag.container()
            .from_("alpine:latest")
            .with_secret_variable("TNR_API_TOKEN", dagger.Secret(token))
            .with_exec(["apk", "add", "curl", "jq"])
        )

        await (
            container
            .with_exec([
                "sh", "-c",
                f"curl -s -X DELETE '{api_url}/pods/{instance_id}' "
                f"-H 'Authorization: Bearer $TNR_API_TOKEN'"
            ])
            .sync()
        )