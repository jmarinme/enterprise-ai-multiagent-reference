// Azure Monitor alerting (PBI-08-01 — resolves Architecture Review Finding A-11: "No alerting
// configuration... found anywhere in ops/bicep/modules/... nothing appears wired to notify a
// human on failure"). Purely additive: one Action Group + three metric alert rules, all on
// metric names confirmed live against this platform's real, already-deployed
// appi-tmxap-dev/ca-tmxap-dev-api resources (`az monitor metrics list-definitions`) — not
// guessed. Touches no existing resource; creating/removing alert rules never affects
// application traffic or data.

@description('Resource name prefix, matching the rest of this platform\'s naming convention (e.g. "tmxap-dev"). Every resource in this module is global-scoped (actionGroups/metricAlerts), so no location parameter is needed.')
param namePrefix string

@description('Resource tags applied for project, environment, purpose, data classification, and ownership traceability.')
param tags object

@description('Resource ID of the existing Application Insights component (requests/failed, requests/duration) to alert on.')
param appInsightsId string

@description('Resource ID of the existing API Container App (Replicas metric) to alert on for availability.')
param apiContainerAppId string

@description('Email address to notify on any alert. Empty string (the default) creates the action group with zero receivers — alert rules still exist and fire (visible in the Azure Portal/Monitor Alerts blade), but nobody is paged until a real operational email is configured here. Deliberately never defaulted to a placeholder/invented address.')
param alertEmailAddress string = ''

@description('Whether to create the alert rules/action group at all. true by default so this finding is actually resolved out of the box; set false only to temporarily disable alerting without removing this module from the template.')
param enabled bool = true

@description('Failed-request count (over a 5-minute window) that triggers the elevated-error-rate alert.')
param errorRateThreshold int = 5

@description('Average request duration in milliseconds (over a 5-minute window) that triggers the high-latency alert.')
param latencyThresholdMs int = 3000

var actionGroupName = 'ag-${namePrefix}-ops'
var hasEmailReceiver = !empty(alertEmailAddress)

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = if (enabled) {
  name: actionGroupName
  location: 'global'
  tags: tags
  properties: {
    groupShortName: take(replace(namePrefix, '-', ''), 12)
    enabled: true
    emailReceivers: hasEmailReceiver
      ? [
          {
            name: 'primary-email'
            emailAddress: alertEmailAddress
            useCommonAlertSchema: true
          }
        ]
      : []
  }
}

resource errorRateAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (enabled) {
  name: 'alert-${namePrefix}-error-rate'
  location: 'global'
  tags: tags
  properties: {
    description: 'Elevated error rate: more than ${errorRateThreshold} failed requests in a 5-minute window (Application Insights requests/failed).'
    severity: 2
    enabled: true
    scopes: [appInsightsId]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          criterionType: 'StaticThresholdCriterion'
          name: 'FailedRequestsCount'
          metricName: 'requests/failed'
          metricNamespace: 'microsoft.insights/components'
          operator: 'GreaterThan'
          threshold: errorRateThreshold
          timeAggregation: 'Count'
        }
      ]
    }
    actions: enabled
      ? [
          {
            actionGroupId: actionGroup.id
          }
        ]
      : []
  }
}

resource latencyAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (enabled) {
  name: 'alert-${namePrefix}-high-latency'
  location: 'global'
  tags: tags
  properties: {
    description: 'High latency: average request duration above ${latencyThresholdMs}ms over a 5-minute window (Application Insights requests/duration).'
    severity: 2
    enabled: true
    scopes: [appInsightsId]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          criterionType: 'StaticThresholdCriterion'
          name: 'AverageRequestDuration'
          metricName: 'requests/duration'
          metricNamespace: 'microsoft.insights/components'
          operator: 'GreaterThan'
          threshold: latencyThresholdMs
          timeAggregation: 'Average'
        }
      ]
    }
    actions: enabled
      ? [
          {
            actionGroupId: actionGroup.id
          }
        ]
      : []
  }
}

// Availability/health (Finding A-11's third requirement). Deliberately NOT an Application
// Insights availability web test (Microsoft.Insights/webtests) — that resource type requires
// hand-authored XML test configuration, real complexity/risk for a "lightweight" alert this
// PBI asks for. Container Apps' own "Replicas" metric (confirmed live against the real,
// deployed ca-tmxap-dev-api resource) is a simpler, equally direct availability signal: zero
// running replicas means the API cannot serve any request at all.
resource availabilityAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (enabled) {
  name: 'alert-${namePrefix}-availability'
  location: 'global'
  tags: tags
  properties: {
    description: 'Availability: the API Container App has zero running replicas over a 5-minute window (Microsoft.App/containerApps Replicas).'
    severity: 1
    enabled: true
    scopes: [apiContainerAppId]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          criterionType: 'StaticThresholdCriterion'
          name: 'NoRunningReplicas'
          metricName: 'Replicas'
          metricNamespace: 'microsoft.app/containerapps'
          operator: 'LessThan'
          threshold: 1
          timeAggregation: 'Average'
        }
      ]
    }
    actions: enabled
      ? [
          {
            actionGroupId: actionGroup.id
          }
        ]
      : []
  }
}

output actionGroupId string = enabled ? actionGroup.id : ''
output errorRateAlertId string = enabled ? errorRateAlert.id : ''
output latencyAlertId string = enabled ? latencyAlert.id : ''
output availabilityAlertId string = enabled ? availabilityAlert.id : ''
