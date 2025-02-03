# Thunder Compute Dagger Module

This Dagger module provides integration with Thunder Compute for running workloads on GPU-enabled Kubernetes nodes.

## Requirements

- Dagger CLI installed
- Thunder API token (TNR_API_TOKEN)

## Usage

```bash
# Deploy a Dagger runner on Thunder Compute
dagger -m github.com/jackowfish/daggerverse/thunder call deploy-dagger-on-thunder \
  --token env:TNR_API_TOKEN \
  --disk-gb 200 \
  --vcpu 8 \
  --memory-gb 32

# The command will return something like:
export _EXPERIMENTAL_DAGGER_RUNNER_HOST=tcp://dagger-xxxxx.thundercompute.com:2375

# Copy and paste the export command to use the Thunder runner
# Now Dagger will execute all function calls using the remote Dagger Engine on Thunder

# When done, destroy the Thunder instance (make sure to note the instance ID from the URL)
dagger -m github.com/jackowfish/daggerverse/thunder call destroy-dagger-on-thunder \
  --token env:TNR_API_TOKEN \
  --instance-id xxxxx
```

## Functions

### deploy-dagger-on-thunder

Deploys a new Dagger runner on Thunder Compute.

Parameters:
- `token` (required): Thunder API token for authentication
- `disk-gb` (required): Disk space in GB
- `vcpu` (required): Number of virtual CPUs
- `memory-gb` (required): Memory in GB

Returns an environment variable command to use the remote runner.

### destroy-dagger-on-thunder

Destroys a Thunder Compute instance.

Parameters:
- `token` (required): Thunder API token for authentication
- `instance-id` (required): ID of the Thunder instance to destroy

## Example

Here's how to use the Thunder module in a workflow:

```bash
# Export your Thunder API token
export TNR_API_TOKEN=your-token-here

# Deploy a Dagger runner with custom resources
dagger -m github.com/jackowfish/daggerverse/thunder call deploy-dagger-on-thunder \
  --token env:TNR_API_TOKEN \
  --disk-gb 500 \
  --vcpu 16 \
  --memory-gb 64

# Copy and paste the returned export command
export _EXPERIMENTAL_DAGGER_RUNNER_HOST=tcp://dagger-xxxxx.thundercompute.com:2375

# Run your Dagger workloads...

# When done, cleanup the instance
dagger -m github.com/jackowfish/daggerverse/thunder call destroy-dagger-on-thunder \
  --token env:TNR_API_TOKEN \
  --instance-id xxxxx