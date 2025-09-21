/* State Management UI Components - Reusable JavaScript for hardware state control */

class StateManager {
    constructor(config) {
        this.apiEndpoint = config.apiEndpoint || '/inverters';
        this.scenarios = config.scenarios || {};
        this.currentActiveScenario = null;
        this.parameterDefinitions = config.parameterDefinitions || {};

        this.init();
    }

    init() {
        this.bindEventListeners();
        this.checkCurrentScenario();

        // Auto-refresh scenario status
        if (this.refreshInterval) {
            setInterval(() => this.checkCurrentScenario(), this.refreshInterval);
        }
    }

    bindEventListeners() {
        // Bind parameter toggle buttons
        document.querySelectorAll('.toggle-parameters').forEach(button => {
            button.addEventListener('click', (e) => {
                const scenarioId = e.target.dataset.scenario;
                this.toggleParameterSection(scenarioId);
            });
        });

        // Bind parameter inputs for validation
        document.querySelectorAll('.parameter-input').forEach(input => {
            input.addEventListener('input', (e) => {
                this.validateParameter(e.target);
            });
        });
    }

    async activateScenario(scenario, customParameters = {}) {
        // Show loading indicator
        this.showLoading(true);
        this.hideMessages();

        // Disable all buttons during processing
        this.setButtonsDisabled(true);

        try {
            // Collect parameter overrides
            const overrides = this.collectParameterOverrides(scenario);
            const mergedParameters = { ...overrides, ...customParameters };

            // Make API call to backend
            const response = await fetch(`${this.apiEndpoint}/activate-scenario`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    scenario: scenario,
                    parameter_overrides: mergedParameters
                })
            });

            const data = await response.json();

            if (data.success) {
                this.setActiveScenario(scenario);
                this.showSuccess(`Scenario ${scenario} activated successfully`);
            } else {
                this.showError(data.error || 'Failed to activate scenario');
            }
        } catch (error) {
            console.error('Error:', error);
            this.showError('Network error: Could not communicate with server');
        } finally {
            this.showLoading(false);
            this.setButtonsDisabled(false);
        }
    }

    setActiveScenario(scenario) {
        // Clear previous active scenario
        if (this.currentActiveScenario) {
            const prevContainer = document.getElementById(`scenario-${this.currentActiveScenario.toLowerCase()}`);
            const prevStatus = document.getElementById(`status-${this.currentActiveScenario.toLowerCase()}`);
            const prevButton = document.getElementById(`btn-${this.currentActiveScenario.toLowerCase()}`);

            if (prevContainer) prevContainer.classList.remove('active');
            if (prevStatus) prevStatus.classList.remove('active');
            if (prevButton) {
                prevButton.classList.remove('active');
                prevButton.textContent = 'Activate';
            }
        }

        // Set new active scenario
        this.currentActiveScenario = scenario;
        const container = document.getElementById(`scenario-${scenario.toLowerCase()}`);
        const status = document.getElementById(`status-${scenario.toLowerCase()}`);
        const button = document.getElementById(`btn-${scenario.toLowerCase()}`);

        if (container) container.classList.add('active');
        if (status) status.classList.add('active');
        if (button) {
            button.classList.add('active');
            button.textContent = 'Active';
        }

        // Update status display
        const scenarioName = this.scenarios[scenario] || scenario;
        const statusDisplay = document.getElementById('current-scenario-display');
        if (statusDisplay) {
            statusDisplay.textContent = `Current Scenario: ${scenario} - ${scenarioName}`;
        }
    }

    toggleParameterSection(scenarioId) {
        const paramSection = document.getElementById(`parameters-${scenarioId.toLowerCase()}`);
        const toggleButton = document.querySelector(`[data-scenario="${scenarioId}"]`);

        if (paramSection && toggleButton) {
            const isVisible = paramSection.classList.contains('visible');

            if (isVisible) {
                paramSection.classList.remove('visible');
                toggleButton.textContent = 'Show Parameters';
            } else {
                paramSection.classList.add('visible');
                toggleButton.textContent = 'Hide Parameters';
            }
        }
    }

    collectParameterOverrides(scenario) {
        const overrides = {};
        const paramSection = document.getElementById(`parameters-${scenario.toLowerCase()}`);

        if (paramSection) {
            const inputs = paramSection.querySelectorAll('.parameter-input');
            inputs.forEach(input => {
                const paramName = input.dataset.parameter;
                const value = input.value.trim();

                if (value !== '' && value !== input.dataset.default) {
                    // Convert value based on parameter type
                    const paramDef = this.parameterDefinitions[paramName];
                    if (paramDef) {
                        if (paramDef.type === 'number') {
                            overrides[paramName] = parseFloat(value);
                        } else if (paramDef.type === 'integer') {
                            overrides[paramName] = parseInt(value);
                        } else {
                            overrides[paramName] = value;
                        }
                    } else {
                        overrides[paramName] = value;
                    }
                }
            });
        }

        return overrides;
    }

    validateParameter(input) {
        const paramName = input.dataset.parameter;
        const value = input.value.trim();
        const paramDef = this.parameterDefinitions[paramName];

        const validationDiv = input.parentElement.querySelector('.parameter-validation');

        if (!paramDef || value === '') {
            this.clearValidation(input, validationDiv);
            return true;
        }

        let isValid = true;
        let errorMessage = '';

        // Type validation
        if (paramDef.type === 'number' || paramDef.type === 'integer') {
            const numValue = parseFloat(value);
            if (isNaN(numValue)) {
                isValid = false;
                errorMessage = `Must be a ${paramDef.type}`;
            } else {
                // Range validation
                if (paramDef.min !== undefined && numValue < paramDef.min) {
                    isValid = false;
                    errorMessage = `Minimum value: ${paramDef.min}`;
                }
                if (paramDef.max !== undefined && numValue > paramDef.max) {
                    isValid = false;
                    errorMessage = `Maximum value: ${paramDef.max}`;
                }
            }
        }

        // Update UI based on validation
        if (isValid) {
            this.clearValidation(input, validationDiv);
        } else {
            this.showValidationError(input, validationDiv, errorMessage);
        }

        return isValid;
    }

    clearValidation(input, validationDiv) {
        input.classList.remove('invalid');
        if (validationDiv) {
            validationDiv.classList.remove('visible');
        }
    }

    showValidationError(input, validationDiv, message) {
        input.classList.add('invalid');
        if (validationDiv) {
            validationDiv.textContent = message;
            validationDiv.classList.add('visible');
        }
    }

    setButtonsDisabled(disabled) {
        const buttons = document.querySelectorAll('.scenario-button');
        buttons.forEach(button => {
            button.disabled = disabled;
        });
    }

    showLoading(show) {
        const indicator = document.getElementById('loading-indicator');
        if (indicator) {
            indicator.style.display = show ? 'block' : 'none';
        }
    }

    showError(message) {
        const errorDiv = document.getElementById('error-message');
        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';

            // Auto-hide after 5 seconds
            setTimeout(() => {
                errorDiv.style.display = 'none';
            }, 5000);
        }
    }

    showSuccess(message) {
        const successDiv = document.getElementById('success-message');
        if (successDiv) {
            successDiv.textContent = message;
            successDiv.style.display = 'block';

            // Auto-hide after 3 seconds
            setTimeout(() => {
                successDiv.style.display = 'none';
            }, 3000);
        }
    }

    hideMessages() {
        const errorDiv = document.getElementById('error-message');
        const successDiv = document.getElementById('success-message');

        if (errorDiv) errorDiv.style.display = 'none';
        if (successDiv) successDiv.style.display = 'none';
    }

    async checkCurrentScenario() {
        try {
            const response = await fetch(`${this.apiEndpoint}/current-scenario`);
            const data = await response.json();

            if (data.success && data.scenario) {
                this.setActiveScenario(data.scenario);
            }
        } catch (error) {
            console.error('Error checking current scenario:', error);
        }
    }
}

// Helper function to create global state manager instance
function createStateManager(config) {
    return new StateManager(config);
}