# Thunder Dagger Module

This Dagger module provides integration with Thunder Compute for running workloads on GPU-enabled Kubernetes nodes.

## Requirements

- Dagger CLI installed
- Thunder API token

## Usage

```bash
# Deploy a Dagger runner on Thunder Compute
dagger -m github.com/jackowfish/thunder-dagger-module call \
  with-token "env:TNR_API_TOKEN" \
  deploy

# The command will return something like:
export _EXPERIMENTAL_DAGGER_RUNNER_HOST=tcp://dagger.thundercompute.org/dagger-worker-xxxxx

# Copy and paste the export command to use the Thunder runner
# Now Dagger will execute all function calls using the remote Dagger Engine on Thunder

# When done, destroy the Thunder instance (make sure to note the instance ID from the URL)
dagger -m github.com/jackowfish/thunder-dagger-module call \
  with-token "env:TNR_API_TOKEN" \
  destroy --instance-id dagger-worker-xxxxx
```

## Functions

### with-token

Configure the Thunder API token.

Parameters:
- `token` (required): Thunder API token for authentication

### with-base-url

Configure a custom base URL (optional).

Parameters:
- `url`: Custom base URL for the Thunder API (defaults to dagger.thundercompute.org)

### deploy

Deploys a new Dagger runner on Thunder Compute.

Returns an environment variable command to use the remote runner.

### destroy

Destroys a Thunder Compute instance.

Parameters:
- `instance-id` (required): ID of the Thunder instance to destroy (in format dagger-worker-xxxxx)

## Example

Here's how to use the Thunder module in a workflow:

```python
import dagger

async def main():
    # Initialize the Thunder client
    thunder = dagger.Connection().thunder().with_token(dagger.Secret("your-token-here"))
    
    # Deploy a runner
    cmd = await thunder.deploy()
    print(f"Run this command: {cmd}")
    
    # Do your work with Dagger...
    
    # When done, cleanup the instance
    # Extract instance ID from the host URL (e.g., dagger-worker-xxxxx)
    await thunder.destroy("dagger-worker-xxxxx")

```

Or using the CLI:

```bash
# Export your Thunder API token
export TNR_API_TOKEN=your-token-here

# Deploy a Dagger runner
dagger -m github.com/jackowfish/thunder-dagger-module call \
  with-token "env:TNR_API_TOKEN" \
  deploy

# Copy and paste the returned export command
export _EXPERIMENTAL_DAGGER_RUNNER_HOST=tcp://dagger.thundercompute.org/dagger-worker-xxxxx

# Run your Dagger workloads...

# When done, cleanup the instance
dagger -m github.com/jackowfish/thunder-dagger-module call \
  with-token "env:TNR_API_TOKEN" \
  destroy --instance-id dagger-worker-xxxxx
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
- Docker socket access
- Required NVIDIA configurations