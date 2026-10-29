{{- define "opspilot.name" -}}
opspilot-agent
{{- end -}}

{{- define "opspilot.labels" -}}
app.kubernetes.io/name: {{ include "opspilot.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "opspilot.selectorLabels" -}}
app: {{ include "opspilot.name" . }}
{{- end -}}
