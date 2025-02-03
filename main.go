package main

import (
	"context"
	"fmt"
	"strings"
	
	"dagger.io/dagger"
)

type Module struct{
	dag *dagger.Client
	baseURL string
}

func New(dag *dagger.Client) *Module {
	return &Module{
		dag: dag,
		baseURL: "dagger.jackdecker.org",
	}
}

// SetBaseURL allows changing the default base URL
func (m *Module) SetBaseURL(url string) {
	m.baseURL = url
}

// DeployDaggerOnThunder creates a new Thunder compute instance with a Dagger runner
func (m *Module) DeployDaggerOnThunder(
	ctx context.Context,
	token *dagger.Secret,
) (string, error) {
	if token == nil {
		return "", fmt.Errorf("TNR_API_TOKEN is required")
	}

	apiURL := fmt.Sprintf("https://%s/api", m.baseURL)

	// Create a base container for making API calls
	base := m.dag.Container().From("alpine:latest").
		WithSecretVariable("TNR_API_TOKEN", token).
		WithExec([]string{"apk", "add", "curl", "jq"})

	// Make API call to Thunder to create instance
	createCmd := fmt.Sprintf(`
		curl -X POST "%s/pods" \
		-H "Authorization: Bearer $TNR_API_TOKEN" \
		-H "Content-Type: application/json" \
		-d '{}' \
		| jq -r '.instance_id'
	`, apiURL)

	result := base.WithExec([]string{"sh", "-c", createCmd})
	instanceID, err := result.Stdout(ctx)
	if err != nil {
		return "", fmt.Errorf("failed to create Thunder instance: %w", err)
	}

	instanceID = strings.TrimSpace(instanceID)

	// Wait for instance to be ready
	waitCmd := fmt.Sprintf(`
		while true; do
			status=$(curl -s -H "Authorization: Bearer $TNR_API_TOKEN" \
				"%s/pods/%s" \
				| jq -r '.status')
			if [ "$status" = "running" ]; then
				break
			fi
			sleep 5
		done
	`, apiURL, instanceID)

	_, err = base.WithExec([]string{"sh", "-c", waitCmd}).Sync(ctx)
	if err != nil {
		return "", fmt.Errorf("failed waiting for instance to be ready: %w", err)
	}

	// Get instance connection details
	getHostCmd := fmt.Sprintf(`
		curl -s -H "Authorization: Bearer $TNR_API_TOKEN" \
		"%s/pods/%s" \
		| jq -r '.host'
	`, apiURL, instanceID)

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
	token *dagger.Secret,
	instanceID string,
) error {
	if token == nil {
		return fmt.Errorf("TNR_API_TOKEN is required")
	}

	apiURL := fmt.Sprintf("https://%s/api", m.baseURL)

	deleteCmd := fmt.Sprintf(`
		curl -X DELETE "%s/pods/%s" \
		-H "Authorization: Bearer $TNR_API_TOKEN"
	`, apiURL, instanceID)

	base := m.dag.Container().From("alpine:latest").
		WithSecretVariable("TNR_API_TOKEN", token).
		WithExec([]string{"apk", "add", "curl"})

	_, err := base.WithExec([]string{"sh", "-c", deleteCmd}).Sync(ctx)
	return err
}