import { ConfigurationSection } from './ConfigurationSection'
import { ConfigurationListItem } from './ConfigurationListItem'

interface ConfigItem {
  key: string
  title: string
  type: string
}

interface ConfigurationStatus {
  isValid: boolean
  errors?: string[]
}

interface ConfigurationListProps {
  integrationConfigs: ConfigItem[]
  llmConfigs: ConfigItem[]
  selectedConfig: string | null
  configStatuses: Record<string, ConfigurationStatus>
  onSelectConfig: (configKey: string) => void
}

export function ConfigurationList({
  integrationConfigs,
  llmConfigs,
  selectedConfig,
  configStatuses,
  onSelectConfig
}: ConfigurationListProps) {
  return (
    <div>
      <ConfigurationSection title="Tools" isFirst>
        {integrationConfigs.map((integration) => (
          <ConfigurationListItem
            key={integration.key}
            configKey={integration.key}
            title={integration.title}
            isSelected={selectedConfig === integration.key}
            status={configStatuses[integration.key]}
            onSelect={onSelectConfig}
          />
        ))}
      </ConfigurationSection>
      
      <ConfigurationSection title="AI Providers">
        {llmConfigs.map((provider) => (
          <ConfigurationListItem
            key={provider.key}
            configKey={provider.key}
            title={provider.title}
            isSelected={selectedConfig === provider.key}
            status={configStatuses[provider.key]}
            onSelect={onSelectConfig}
          />
        ))}
      </ConfigurationSection>
    </div>
  )
}