'use client';

import { useEffect } from 'react';
import { Button, Dropdown, DropdownTrigger, DropdownMenu, DropdownItem, Tooltip, ButtonGroup, Divider } from '@heroui/react';
import { ChevronDownIcon } from '@heroicons/react/24/outline';
import { ModelName, ModelMode, getAgentModeModels, getRegularModeModels, MODEL_CONFIGS, ReasoningLevel, Provider } from '@/lib/types';
import { useModelSelection } from '@/hooks/useModelSelection';
import { useAgentMode } from '@/hooks/useAgentMode';

// Reasoning level display names
const REASONING_LABELS: Record<ReasoningLevel, string> = {
  [ReasoningLevel.NONE]: 'None',
  [ReasoningLevel.LOW]: 'Low',
  [ReasoningLevel.MEDIUM]: 'Medium',
  [ReasoningLevel.HIGH]: 'High',
};

interface ModelSelectorProps {
  isOpen?: boolean;
  onOpenChange?: (isOpen: boolean) => void;
}

export function ModelSelector({ isOpen, onOpenChange }: ModelSelectorProps) {
  const { selectedModel, setSelectedModel, reasoningLevel, setReasoningLevel } = useModelSelection();
  const { isAgentMode } = useAgentMode();

  // Get available models based on mode
  const availableModels = isAgentMode ? getAgentModeModels() : getRegularModeModels();
  const availableModelIds = availableModels.map(model => model.id);

  // Reset to default model if current selection is not available in current mode
  useEffect(() => {
    const currentModel = availableModelIds.includes(selectedModel)
      ? selectedModel
      : ModelName.CLAUDE_HAIKU_4_5;

    if (currentModel !== selectedModel) {
      setSelectedModel(currentModel);
    }
  }, [isAgentMode, selectedModel, setSelectedModel, availableModelIds]);

  // Use the current model for display
  const currentModel = availableModelIds.includes(selectedModel)
    ? selectedModel
    : ModelName.CLAUDE_HAIKU_4_5;

  const currentModelConfig = MODEL_CONFIGS[currentModel];

  const handleModelSelect = (key: React.Key) => {
    setSelectedModel(key as ModelName);
  };

  // Check if a specific model supports OpenAI reasoning (None/Low/Medium/High)
  const modelSupportsOpenAIReasoning = (modelId: ModelName) => {
    const modelConfig = MODEL_CONFIGS[modelId];
    return modelConfig?.provider === Provider.OPENAI && modelId === ModelName.GPT5_2;
  };

  // Check if a specific model supports Anthropic reasoning (Low/Medium/High only)
  const modelSupportsAnthropicReasoning = (modelId: ModelName) => {
    const modelConfig = MODEL_CONFIGS[modelId];
    return modelConfig?.provider === Provider.ANTHROPIC && modelId === ModelName.CLAUDE_HAIKU_4_5;
  };

  // Check if a specific model supports xAI-style reasoning (None/Medium only)
  const modelSupportsXAIReasoning = (modelId: ModelName) => {
    const modelConfig = MODEL_CONFIGS[modelId];
    return modelConfig?.provider === Provider.XAI && modelId === ModelName.XAI_GROK_4_1_FAST;
  };

  // Check if a specific model supports Google reasoning (Low/Medium/High)
  const modelSupportsGoogleReasoning = (modelId: ModelName) => {
    const modelConfig = MODEL_CONFIGS[modelId];
    return modelConfig?.provider === Provider.GOOGLE && modelId === ModelName.GEMINI_3_FLASH;
  };

  // Get available reasoning levels for a specific model
  const getAvailableReasoningLevels = (modelId: ModelName): ReasoningLevel[] => {
    if (modelSupportsOpenAIReasoning(modelId)) {
      return [ReasoningLevel.NONE, ReasoningLevel.LOW, ReasoningLevel.MEDIUM, ReasoningLevel.HIGH];
    }
    if (modelSupportsAnthropicReasoning(modelId)) {
      return [ReasoningLevel.LOW, ReasoningLevel.MEDIUM, ReasoningLevel.HIGH];
    }
    if (modelSupportsXAIReasoning(modelId)) {
      return [ReasoningLevel.NONE, ReasoningLevel.MEDIUM];
    }
    if (modelSupportsGoogleReasoning(modelId)) {
      return [ReasoningLevel.LOW, ReasoningLevel.MEDIUM, ReasoningLevel.HIGH];
    }
    return []; // Model doesn't support reasoning levels
  };

  // Get default reasoning level for a model
  const getDefaultReasoningLevel = (modelId: ModelName): ReasoningLevel => {
    if (modelSupportsOpenAIReasoning(modelId)) {
      return ReasoningLevel.MEDIUM;
    }
    if (modelSupportsAnthropicReasoning(modelId)) {
      return ReasoningLevel.MEDIUM;
    }
    if (modelSupportsXAIReasoning(modelId)) {
      return ReasoningLevel.NONE;
    }
    if (modelSupportsGoogleReasoning(modelId)) {
      return ReasoningLevel.MEDIUM;
    }
    return ReasoningLevel.MEDIUM; // Fallback default
  };

  // Reset reasoning level when changing models if current level is not available
  useEffect(() => {
    const availableLevels = getAvailableReasoningLevels(currentModel);
    
    // If the model has reasoning levels and current level is not available, reset to default
    if (availableLevels.length > 0 && !availableLevels.includes(reasoningLevel)) {
      setReasoningLevel(getDefaultReasoningLevel(currentModel));
    }
  }, [currentModel, reasoningLevel, setReasoningLevel]);

  return (
    <Dropdown 
      placement="bottom-start"
      size="sm"
      className="bg-background"
      isOpen={isOpen}
      onOpenChange={onOpenChange}
    >
      <DropdownTrigger>
        <Button
          variant="light"
          radius="full"
          size="sm"
          className="text-default-500 cursor-pointer min-w-[90px] max-w-[120px] sm:max-w-none flex-shrink-0 justify-start px-3"
          endContent={<ChevronDownIcon className="w-3 h-3 opacity-60 flex-shrink-0" />}
        >
          <Tooltip content="Select model" placement="top" size="sm">
            <span className="text-xs truncate sm:whitespace-nowrap">
              {currentModelConfig?.displayName || 'Select Model'}
            </span>
          </Tooltip>
        </Button>
      </DropdownTrigger>
      <DropdownMenu
        variant="light"
        className="min-w-[300px]"
        selectedKeys={[currentModel]}
        selectionMode="single"
        onSelectionChange={(keys) => {
          const selectedKey = Array.from(keys)[0];
          if (selectedKey) {
            handleModelSelect(selectedKey);
          }
        }}
      >
      {availableModels.map((modelConfig, index) => {
        const hasOpenAIReasoning = modelSupportsOpenAIReasoning(modelConfig.id);
        const hasAnthropicReasoning = modelSupportsAnthropicReasoning(modelConfig.id);
        const hasXAIReasoning = modelSupportsXAIReasoning(modelConfig.id);
        const hasGoogleReasoning = modelSupportsGoogleReasoning(modelConfig.id);
        const isLastItem = index === availableModels.length - 1;
        
        return (
          <DropdownItem
            key={modelConfig.id}
            className="text-xs"
            textValue={modelConfig.displayName}
            closeOnSelect={false}
          >
            <div className="flex flex-col gap-2 w-full">
              <Tooltip 
                content={modelConfig.description}
                placement="right"
                size="sm"
              >
                <span className="text-xs font-medium">{modelConfig.displayName}</span>
              </Tooltip>
              
              {/* Show OpenAI reasoning button group (None/Low/Medium/High) */}
              {hasOpenAIReasoning && currentModel === modelConfig.id && (
                <div className="flex flex-col gap-1 mt-1 pb-1" onClick={(e) => e.stopPropagation()}>
                  <Tooltip content="Choose reasoning level" placement="right" size="sm">
                    <ButtonGroup size="sm" className="w-full bg-secondary rounded-xl" variant="light">
                      <Button
                        color={reasoningLevel === ReasoningLevel.NONE ? "primary" : "default"}
                        className={`${reasoningLevel === ReasoningLevel.NONE ? "bg-primary/20" : "bg-secondary"} flex w-full`}
                        onPress={() => setReasoningLevel(ReasoningLevel.NONE)}
                      >
                        <span className="text-[10px]">{REASONING_LABELS[ReasoningLevel.NONE]}</span>
                      </Button>
                      <Button
                        color={reasoningLevel === ReasoningLevel.LOW ? "primary" : "default"}
                        className={`${reasoningLevel === ReasoningLevel.LOW ? "bg-primary/20" : "bg-secondary"} flex w-full`}
                        onPress={() => setReasoningLevel(ReasoningLevel.LOW)}
                      >
                        <span className="text-[10px]">{REASONING_LABELS[ReasoningLevel.LOW]}</span>
                      </Button>
                      <Button
                        color={reasoningLevel === ReasoningLevel.MEDIUM ? "primary" : "default"}
                        className={`${reasoningLevel === ReasoningLevel.MEDIUM ? "bg-primary/20" : "bg-secondary"} flex w-full`}
                        onPress={() => setReasoningLevel(ReasoningLevel.MEDIUM)}
                      >
                        <span className="text-[10px]">{REASONING_LABELS[ReasoningLevel.MEDIUM]}</span>
                      </Button>
                      <Button
                        color={reasoningLevel === ReasoningLevel.HIGH ? "primary" : "default"}
                        className={`${reasoningLevel === ReasoningLevel.HIGH ? "bg-primary/20" : "bg-secondary"} flex w-full`}
                        onPress={() => setReasoningLevel(ReasoningLevel.HIGH)}
                      >
                        <span className="text-[10px]">{REASONING_LABELS[ReasoningLevel.HIGH]}</span>
                      </Button>
                    </ButtonGroup>
                  </Tooltip>
                </div>
              )}

              {/* Show Anthropic reasoning button group (Low/Medium/High only) */}
              {hasAnthropicReasoning && currentModel === modelConfig.id && (
                <div className="flex flex-col gap-1 mt-1 pb-1" onClick={(e) => e.stopPropagation()}>
                  <Tooltip content="Choose reasoning level" placement="right" size="sm">
                    <ButtonGroup size="sm" className="w-full bg-secondary rounded-xl" variant="light">
                      <Button
                        color={reasoningLevel === ReasoningLevel.LOW ? "primary" : "default"}
                        className={`${reasoningLevel === ReasoningLevel.LOW ? "bg-primary/20" : "bg-secondary"} flex w-full`}
                        onPress={() => setReasoningLevel(ReasoningLevel.LOW)}
                      >
                        <span className="text-[10px]">{REASONING_LABELS[ReasoningLevel.LOW]}</span>
                      </Button>
                      <Button
                        color={reasoningLevel === ReasoningLevel.MEDIUM ? "primary" : "default"}
                        className={`${reasoningLevel === ReasoningLevel.MEDIUM ? "bg-primary/20" : "bg-secondary"} flex w-full`}
                        onPress={() => setReasoningLevel(ReasoningLevel.MEDIUM)}
                      >
                        <span className="text-[10px]">{REASONING_LABELS[ReasoningLevel.MEDIUM]}</span>
                      </Button>
                      <Button
                        color={reasoningLevel === ReasoningLevel.HIGH ? "primary" : "default"}
                        className={`${reasoningLevel === ReasoningLevel.HIGH ? "bg-primary/20" : "bg-secondary"} flex w-full`}
                        onPress={() => setReasoningLevel(ReasoningLevel.HIGH)}
                      >
                        <span className="text-[10px]">{REASONING_LABELS[ReasoningLevel.HIGH]}</span>
                      </Button>
                    </ButtonGroup>
                  </Tooltip>
                </div>
              )}

              {/* Show xAI reasoning button group (None/Medium only) */}
              {hasXAIReasoning && currentModel === modelConfig.id && (
                <div className="flex flex-col gap-1 mt-1 pb-1" onClick={(e) => e.stopPropagation()}>
                  <Tooltip content="Toggle reasoning mode" placement="right" size="sm">
                    <ButtonGroup size="sm" className="w-full bg-secondary rounded-xl" variant="light">
                      <Button
                        color={reasoningLevel === ReasoningLevel.NONE ? "primary" : "default"}
                        className={`${reasoningLevel === ReasoningLevel.NONE ? "bg-primary/20" : "bg-secondary"} flex w-full`}
                        onPress={() => setReasoningLevel(ReasoningLevel.NONE)}
                      >
                        <span className="text-[10px]">Fast</span>
                      </Button>
                      <Button
                        color={reasoningLevel === ReasoningLevel.MEDIUM ? "primary" : "default"}
                        className={`${reasoningLevel === ReasoningLevel.MEDIUM ? "bg-primary/20" : "bg-secondary"} flex w-full`}
                        onPress={() => setReasoningLevel(ReasoningLevel.MEDIUM)}
                      >
                        <span className="text-[10px]">Reasoning</span>
                      </Button>
                    </ButtonGroup>
                  </Tooltip>
                </div>
              )}

              {/* Show Google reasoning button group (Low/Medium/High) */}
              {hasGoogleReasoning && currentModel === modelConfig.id && (
                <div className="flex flex-col gap-1 mt-1 pb-1" onClick={(e) => e.stopPropagation()}>
                  <Tooltip content="Choose reasoning level" placement="right" size="sm">
                    <ButtonGroup size="sm" className="w-full bg-secondary rounded-xl" variant="light">
                      <Button
                        color={reasoningLevel === ReasoningLevel.LOW ? "primary" : "default"}
                        className={`${reasoningLevel === ReasoningLevel.LOW ? "bg-primary/20" : "bg-secondary"} flex w-full`}
                        onPress={() => setReasoningLevel(ReasoningLevel.LOW)}
                      >
                        <span className="text-[10px]">{REASONING_LABELS[ReasoningLevel.LOW]}</span>
                      </Button>
                      <Button
                        color={reasoningLevel === ReasoningLevel.MEDIUM ? "primary" : "default"}
                        className={`${reasoningLevel === ReasoningLevel.MEDIUM ? "bg-primary/20" : "bg-secondary"} flex w-full`}
                        onPress={() => setReasoningLevel(ReasoningLevel.MEDIUM)}
                      >
                        <span className="text-[10px]">{REASONING_LABELS[ReasoningLevel.MEDIUM]}</span>
                      </Button>
                      <Button
                        color={reasoningLevel === ReasoningLevel.HIGH ? "primary" : "default"}
                        className={`${reasoningLevel === ReasoningLevel.HIGH ? "bg-primary/20" : "bg-secondary"} flex w-full`}
                        onPress={() => setReasoningLevel(ReasoningLevel.HIGH)}
                      >
                        <span className="text-[10px]">{REASONING_LABELS[ReasoningLevel.HIGH]}</span>
                      </Button>
                    </ButtonGroup>
                  </Tooltip>
                </div>
              )}

              {/* Divider between items */}
              {!isLastItem && <Divider className="mt-2" />}
            </div>
          </DropdownItem>
        );
      })}
      </DropdownMenu>
    </Dropdown>
  );
}
