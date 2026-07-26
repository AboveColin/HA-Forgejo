# Forgejo for Home Assistant

Monitor a [Forgejo](https://forgejo.org/) instance from Home Assistant: unread
notifications, open issues and pull requests per repository, and whether the
last CI run passed.

Forgejo keeps API compatibility with **Gitea**, so this works against a Gitea
instance too. Codeberg is a public Forgejo instance and works as well.

Unaffiliated with the Forgejo project.

[![hassfest](https://github.com/AboveColin/HA-Forgejo/actions/workflows/main.yml/badge.svg)](https://github.com/AboveColin/HA-Forgejo/actions/workflows/main.yml)
[![HACS](https://github.com/AboveColin/HA-Forgejo/actions/workflows/HACSAction.yml/badge.svg)](https://github.com/AboveColin/HA-Forgejo/actions/workflows/HACSAction.yml)

## Install

### HACS

1. HACS → **⋮** → **Custom repositories**
2. Add `https://github.com/AboveColin/HA-Forgejo`, category **Integration**
3. Install **Forgejo**, then restart Home Assistant
4. **Settings → Devices & Services → Add Integration → Forgejo**

### Manually

Copy `custom_components/forgejo` into your `config/custom_components/` folder
and restart Home Assistant.

## Set up

You need an API token. In Forgejo: **Settings → Applications → Generate New
Token**. Read-only scopes are enough, and are what you should use:

- `read:repository`
- `read:issue`
- `read:notification`
- `read:user`

Then add the integration and fill in:

| Field | Example | Notes |
|---|---|---|
| Address | `https://git.example.com` | The web address, not the API path. Pasting `/api/v1` on the end is fine — it gets stripped. |
| API token | `a1b2c3…` | The token you just made |
| Verify the SSL certificate | on | Turn off only for a self-signed certificate on your own network |

After setup, open the integration's **Configure** button to choose which
repositories you want entities for. Nothing is tracked until you pick something
— an instance can have hundreds of repositories and polling all of them would
be rude.

## Entities

One device for the instance:

| Entity | Description |
|---|---|
| Unread notifications | Your unread notification count |
| Version | Instance version (diagnostic) |

One device per tracked repository:

| Entity | Description |
|---|---|
| Open issues | Open issues, **not** counting pull requests |
| Open pull requests | Open pull requests |
| Stars | Stargazers |
| Forks | Forks (disabled by default) |
| Releases | Published releases (disabled by default) |
| Size | Repository size (disabled by default) |
| Last commit | Timestamp of the tip commit, with sha, message and author as attributes |
| Latest run status | Status of the most recent Actions run, with workflow, branch and run number as attributes |
| CI failing | `Problem` — on when the last finished run failed |
| CI running | `Running` — on while a run is in progress (disabled by default) |

Entities that are off by default can be turned on individually from the device
page.

The two CI entities are **unknown**, not "off", when a repository has no
Actions runs or its current run has not finished. A run that is still going has
not passed, and saying otherwise would make an automation fire early.

## Automation example

Get a notification when CI breaks on a repository you care about:

```yaml
automation:
  - alias: "CI broke"
    triggers:
      - trigger: state
        entity_id: binary_sensor.example_repo_ci_failing
        to: "on"
    actions:
      - action: notify.mobile_app_phone
        data:
          title: "CI failed"
          message: >-
            {{ state_attr('sensor.example_repo_latest_run_status', 'workflow') }}
            failed on {{ state_attr('sensor.example_repo_latest_run_status', 'branch') }}
```

## Polling

Every tracked repository costs three requests per refresh, and the refresh runs
every five minutes. Ten repositories is about 360 requests an hour. That is
fine for an instance you run yourself; be more conservative against a shared
public one.

## Troubleshooting

**"The address answered, but not like a Forgejo instance"** — something other
than Forgejo replied. Usually an authentication proxy in front of the instance
returning its own login page. Allow `/api/v1` through unauthenticated, or point
Home Assistant at the instance directly.

**"The token was rejected"** — either the token is wrong, or it is missing one
of the four read scopes. Tokens cannot be edited after creation; make a new one.

**Nothing but the two instance entities appeared** — no repositories are
selected yet. Use the **Configure** button.

**A repository's entities went unavailable** — it was renamed, deleted, or made
private to an account the token cannot see. The other repositories keep working.

For a bug report, attach diagnostics from the integration's ⋮ menu. Repository
names, commit messages and your address are stripped out of that file.

## Credits

Uses the [`forgejo`](https://github.com/AboveColin/forgejo) client library.

## License

MIT
