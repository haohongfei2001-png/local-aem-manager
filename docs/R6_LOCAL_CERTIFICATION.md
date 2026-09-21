# R6 Local Chrome Certification Harness

This harness exists so the real-browser certification can be executed without changing R6 code after local access is restored.

## Safety

Use:
- real developer threads for observation only;
- one dedicated harmless ChatGPT certification thread for send probes.

Do not run send probes against PAIA, PJSDAS, HCL, or another active engineering thread.

The certification sends three unique messages to the dedicated thread:

1. normal send and positive confirmation;
2. injected pre-send failure followed by a permitted retry;
3. real send click followed by injected post-send uncertainty, then proof that automatic retry is blocked.

## Prerequisites

- Chrome already running with the intended user profile/session;
- Chrome DevTools endpoint available;
- Python package installed with the browser extra:
  `pip install -e ".[browser]"`;
- current browser selectors confirmed against the live page;
- a dedicated certification chat open in the same browser profile.

Do not hard-code account cookies, session tokens, or credentials.

## Configuration

Copy:

`config/r6-cert.example.yaml`

to a local file outside the repository, for example:

`~/.config/local-aem-manager/r6-cert.yaml`

Fill:
- CDP endpoint;
- current DOM selectors;
- observe-only developer thread URLs;
- dedicated certification thread URL.

Do not commit the completed local file.

## Execute

Run:

`local-aem-r6-cert --config ~/.config/local-aem-manager/r6-cert.yaml`

A passing run verifies:

- current CDP attach;
- configured thread mapping;
- real thread observation;
- refresh/rebind;
- normal exactly-once send;
- pre-send retry;
- post-send-unknown no-retry;
- controlled writer-lease stale takeover path.

## Certification boundary

A passing harness run is necessary but the manager should still inspect the resulting JSON and durable evidence before changing canonical R6 to COMPLETE.

The current GitHub/CI tests do not count as a substitute for this local run.
