> Please note that this is a WIP for an MVP to get Dagger working on ThunderCompute. This uses a custom dagger engine here: https://github.com/jackowfish/thunder-dagger

# Thunder Dagger Module

This Dagger module provides integration with Thunder Compute for running workloads on GPU-enabled Kubernetes nodes.

## Requirements

- Dagger CLI installed
- Thunder API token

## Usage

```bash
# Deploy a Dagger runner on Thunder Compute
dagger -m github.com/jackowfish/thunder-dagger-module call deploy \
  --token "$TNR_API_TOKEN" | bash

# The command will return something like:
export _EXPERIMENTAL_DAGGER_RUNNER_HOST=ssh://<ip>:<port>

# Copy and paste the export command to use the Thunder runner
# Now Dagger will execute all function calls using the remote Dagger Engine on Thunder

# When done, destroy the Thunder instance (make sure to note the instance ID from the URL)
dagger -m github.com/jackowfish/thunder-dagger-module call destroy \
  --token "$TNR_API_TOKEN" \
  --instance-id dagger-worker-xxxxx
```

## Functions

### deploy

Deploys a new Dagger runner on Thunder Compute.

Parameters:
- `token` (required): Thunder API token for authentication

Returns an environment variable command to use the remote runner.

### destroy

Destroys a Thunder Compute instance.

Parameters:
- `token` (required): Thunder API token for authentication
- `instance-id` (required): ID of the Thunder instance to destroy (in format dagger-worker-xxxxx)

## Example

Here's how to use the Thunder module in a workflow:

```python
import dagger

async def main():
    # Initialize the Thunder client
    thunder = dagger.Connection().thunder()
    
    # Deploy a runner
    cmd = await thunder.with_token("your-token-here").deploy()
    print(f"Run this command: {cmd}")
    
    # Do your work with Dagger...
    
    # When done, cleanup the instance
    # Extract instance ID from the host URL (e.g., dagger-worker-xxxxx)
    await thunder.with_token("your-token-here").destroy("dagger-worker-xxxxx")

```

## API Details

The module interacts with the Thunder API to:
1. Create a new GPU-enabled pod
2. Wait for the pod to be ready
3. Return the connection URL
4. Allow cleanup when done

The pods are automatically configured with:
- GPU support enabled
- 4 vCPUs
- 16GB memory
