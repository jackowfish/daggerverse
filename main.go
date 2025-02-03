package main

import (
	"context"
	"fmt"
	"strings"
)

type Module struct{}

// DeployDaggerOnThunder creates a new Thunder compute instance with a Dagger runner
func (m *Module) DeployDaggerOnThunder(
	ctx context.Context,
	token *Secret,
) (string, error) {
	if token == nil {
		return "", fmt.Errorf("TNR_API_TOKEN is required")
	}

	// Create a base container for making API calls
	base := dag.Container().From("alpine:latest").
		WithSecretVariable("TNR_API_TOKEN", token).
		WithExec([]string{"apk", "add", "curl", "jq"})

	// Make API call to Thunder to create instance
	createCmd := `
		curl -X POST "https://dagger.thundercompute.com/api/pods" \
		-H "Authorization: Bearer $TNR_API_TOKEN" \
		-H "Content-Type: application/json" \
		-d '{}' \
		| jq -r '.instance_id'
	`

	result := base.WithExec([]string{"sh", "-c", createCmd})
	instanceID, err := result.Stdout(ctx)
	if err != nil {
		return "", fmt.Errorf("failed to create Thunder instance: %w", err)
	}

	// Wait for instance to be ready
	waitCmd := fmt.Sprintf(`
		while true; do
			status=$(curl -s -H "Authorization: Bearer $TNR_API_TOKEN" \
				"https://dagger.thundercompute.com/api/pods/%s" \
				| jq -r '.status')
			if [ "$status" = "running" ]; then
				break
			fi
			sleep 5
		done
	`, strings.TrimSpace(instanceID))

	base = base.WithExec([]string{"sh", "-c", waitCmd})

	// Get instance connection details
	getHostCmd := fmt.Sprintf(`
		curl -s -H "Authorization: Bearer $TNR_API_TOKEN" \
		"https://dagger.thundercompute.com/api/pods/%s" \
		| jq -r '.host'
	`, strings.TrimSpace(instanceID))

	result = base.WithExec([]string{"sh", "-c", getHostCmd})
	host, err := result.Stdout(ctx)
	if err != nil {
		return "", fmt.Errorf("failed to get instance host: %w", err)
	}

	// Return the environment variable command to use the runner
	return fmt.Sprintf("export _EXPERIMENTAL_DAGGER_RUNNER_HOST=%s", strings.TrimSpace(host)), nil
}

// DestroyDaggerOnThunder destroys a Thunder compute instance
func (m *Module) DestroyDaggerOnThunder(
	ctx context.Context,
	token *Secret,
	instanceID string,
) error {
	if token == nil {
		return fmt.Errorf("TNR_API_TOKEN is required")
	}

	deleteCmd := fmt.Sprintf(`
		curl -X DELETE "https://dagger.thundercompute.com/api/pods/%s" \
		-H "Authorization: Bearer $TNR_API_TOKEN"
	`, instanceID)

	base := dag.Container().From("alpine:latest").
		WithSecretVariable("TNR_API_TOKEN", token).
		WithExec([]string{"apk", "add", "curl"}).
		WithExec([]string{"sh", "-c", deleteCmd})

	_, err := base.Sync(ctx)
	return err
}