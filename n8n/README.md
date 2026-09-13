# Orchestration with n8n

Milestone J4.3. This is the one piece of infrastructure in the project, and the
only one that touches a server running somebody's production workload.

Everything here answers a single question: **how does a scheduler that cannot
see the code get the pipeline to run?**

---

## 1. Why this is not a workflow problem

The obvious design — an n8n *Execute Command* node running
`python -m ingestion...` — cannot work here, and the reasons were measured on
the server on 2026-09-13 rather than assumed:

| Measurement | Consequence |
|---|---|
| The n8n container has **no Docker socket** mounted | n8n cannot start a container, and mounting the socket would hand every workflow on this host the equivalent of root |
| n8n sits on network `root_default`, the database on `mhi_default`, published on the server **loopback only** | a Postgres node in n8n **cannot reach our database at all** |
| *Execute Command* runs **inside** the n8n container | that container has neither this project nor its dependencies |
| `/opt/mhi` held `.env`, `docker-compose.yml` and `sql/` | not one line of Python was on the server |
| `python3` is 3.12.3 but `python3 -m venv` **fails** on missing `ensurepip` | the host cannot run the code as it stands either (and `venv --help` answers fine, which is how the trap hides) |

The third row has a consequence that shapes the whole workflow: **the verdict of
a run cannot be read from the database.** It has to travel back through an exit
code.

---

## 2. The shape that results

```
   n8n container (production, untouched)
   ┌──────────────────────────────────────┐
   │  Schedule Trigger   Monday 06:00     │
   │           ↓                          │
   │  SSH node → 172.18.0.1:22            │   the Docker gateway: how a
   │           ↓                          │   container reaches its host
   │  Code node: throw if exit ≠ 0        │
   └──────────────────────────────────────┘
               ↓  ssh, restricted key
   host sshd
               ↓  forced command, whitelist
   /opt/mhi/bin/vps-pipeline.sh
               ↓  docker compose run --rm
   mhi-runner container ── network mhi_default ──→ mhi-postgres
        python -m ingestion...
        dbt build
```

Three facts hold this together:

* **The runner is a container, not a virtualenv.** It pins Python to 3.14.6,
  the exact version the project is developed on, and installs from
  `requirements.lock.txt` — equal to the laptop rather than merely similar. No
  `apt` on the host, no system dependency to maintain.
* **The code is bind-mounted read-only.** `git log` in `/opt/mhi/repo` answers
  which commit is executing; a fix is a deploy rather than a rebuild; and the
  pipeline cannot rewrite its own source.
* **The key can only do one thing.** See section 5.

---

## 3. The tasks

`scripts/vps-pipeline.sh` accepts exactly six words. Anything else is refused
without being interpreted.

| Task | What it does |
|---|---|
| `refresh` | Bank of Canada, StatCan CPI, APCIQ, then **one** `dbt build`. This is what the schedule calls. |
| `bank-of-canada` | that source alone, then `dbt build` |
| `statcan-cpi` | that source alone, then `dbt build` |
| `apciq` | that source alone, then `dbt build` |
| `dbt-build` | transformations and tests only, no ingestion |
| `status` | read-only: deployed commit and container state |

**Only three sources are scheduled, and that is a measurement.** The other five
— the 2021 census, the geographic attribute file, the administrative
boundaries, the neighbourhoods, the tract boundaries — are frozen. Re-running
them would re-download hundreds of megabytes to insert zero rows. They remain
available as manual commands.

**One `dbt build` after all ingestion, never one per source.** The models are
cross-dependent: the CPI restates APCIQ prices, so building a new APCIQ quarter
before the CPI that indexes it can fail
`assert_every_priced_quarter_can_be_indexed` transiently.

### Exit codes

n8n cannot ask the database how a run went, so the exit code carries the
verdict:

| Code | Meaning |
|---|---|
| `0` | everything succeeded |
| `64` | the requested task is not on the whitelist |
| `69` | another run holds the lock |
| `70` | an ingestion step or the dbt build failed |

---

## 4. Running it

From the laptop, in **Git Bash**:

```bash
bash scripts/deploy-vps.sh          # ship the current commit, build the image
bash scripts/vps-run.sh status      # read-only check
bash scripts/vps-run.sh refresh     # the full pipeline
```

`deploy-vps.sh` ships **`git archive HEAD`** — the contents of the current
commit, piped into tar over SSH. That is a structural guarantee rather than a
list of exclusions to maintain:

* `.env` is untracked, so it **cannot** be shipped. Neither can `.venv/`,
  `data/`, or anything a `.gitignore` rule covers.
* Uncommitted work cannot be shipped either: the script refuses a dirty tree.
  What runs on the server is always a commit you can name.

Measured on 2026-09-13, first run on the server:

| | |
|---|---|
| `refresh`, cold cache | **192 s**, exit 0 |
| of which the 29 APCIQ PDFs | ~183 MB downloaded and parsed |
| `dbt build` alone | **34 s**, `PASS=353 ERROR=0` |
| replay of all three sources | **0 inserted, 0 updated** |

---

## 5. The key n8n uses, and why it is safe

`bash scripts/setup-n8n-key.sh` creates a dedicated key and installs it with
three restrictions:

```
restrict,from="172.18.0.0/16",command="/opt/mhi/bin/vps-pipeline.sh" ssh-ed25519 AAAA...
```

* **`command=`** — sshd runs *that* script and ignores whatever the client
  asked for, putting the request in `SSH_ORIGINAL_COMMAND`. The script matches
  it against the six-word whitelist and **never** evaluates, expands or shells
  it out.
* **`restrict`** — every forwarding off, no pty, no user rc file.
* **`from=`** — refused from anywhere but the Docker subnet. This host has no
  firewall (verified in J2) and sshd listens on `0.0.0.0:22`, so without this a
  leaked key would be usable from the internet.

The private key is written to `~/.ssh/id_ed25519_mhi_n8n` on the laptop. It is
never printed by the script, never committed, and pasting it into n8n is a
manual step done by a human.

### What has been proven, and what has not

| Claim | Status |
|---|---|
| The whitelist refuses injection (`refresh; rm -rf /`, `cat /etc/shadow`, an empty task) | **proven**, exit 64, string printed escaped, never interpreted |
| The forced command intercepts an arbitrary request and runs the pipeline instead | **proven** — asked for `status` over SSH with that key, got the pipeline |
| `from=` refuses this laptop | **proven**, refused before authentication |
| sshd sees n8n as `172.18.0.5`, inside `172.18.0.0/16` | **measured** in the sshd log |
| The two together, from the n8n container | **proven on 2026-09-13** — the first execution from n8n asked for `status` and got the pipeline, `exitCode: 0` |
| The `cd <cwd> ;` prefix is tolerated in real conditions | **proven** — every execution from n8n ran with *Working Directory* left at `/`, so the server received `cd / ; refresh` and accepted it |

---

## 6. Wiring it up in n8n

1. **Credential** — *Credentials > New > SSH*, type **Private Key**:

   | Field | Value |
   |---|---|
   | Host | `172.18.0.1` |
   | Port | `22` |
   | Username | `root` |
   | Private key | paste the contents of `~/.ssh/id_ed25519_mhi_n8n` |

   Print it yourself, in Git Bash: `cat ~/.ssh/id_ed25519_mhi_n8n`

2. **Import** `workflows/mhi-refresh.json`, then select the credential you just
   created on the SSH node. The workflow arrives **inactive** on purpose.

3. **Leave the SSH node's *Working Directory* empty.** The library underneath
   it rewrites the command as `cd <cwd> ; <command>` when that field is set, so
   `refresh` would arrive as `cd / ; refresh`. The script tolerates exactly that
   prefix — it recognises and discards it, never executes it — but an empty
   field avoids the question.

4. **Notification.** The workflow does not know which channel you use, on
   purpose. Its last node *throws* when the pipeline failed, which fails the
   execution and fires whatever is set under *Settings > Error Workflow*. Point
   that at a workflow containing an *Error Trigger* and your Telegram node, and
   the channel can change without this workflow ever changing.

   The thrown message already carries the exit code, its meaning, and the full
   pipeline output — so the notification is a diagnosis, not an alarm. Truncate
   it in the notification node: Telegram refuses a message over 4096 characters,
   and a failed `dbt build` produces far more than that, so the one alert that
   matters most would be the one that never arrives.

   **The alerting workflow is deliberately NOT in this repository.** It carries
   a chat ID, which is a personal identifier; `mhi-refresh.json` carries none.
   Same rule as the `.pbix` holding APCIQ figures: what cannot be public stays
   out of git.

5. **Activate**, and run it once by hand first.

> **The Code node is not decoration.** The SSH node does **not** fail on a
> non-zero exit code: it returns `{ stdout, stderr, code, signal }` as data
> (read in the n8n and node-ssh sources on 2026-09-13). Without that node, a
> pipeline that failed every step would still leave a **green** execution. On a
> weekly schedule nobody watches, that is the worst available outcome.

---

## 7. When something breaks

| Symptom | Cause |
|---|---|
| `Permission denied (publickey)` from the SSH node | the `from=` clause. Docker renumbered the network: check with `docker inspect -f '{{range .NetworkSettings.Networks}}{{.Gateway}}{{end}}' root-n8n-1` and re-run `MHI_N8N_FROM=<subnet> bash scripts/setup-n8n-key.sh` |
| `REFUSED: ... is not an allowed task` | the SSH node sent something other than a bare task name — usually a non-empty *Working Directory*, or a typo |
| exit `69` | a previous run is still going. The lock is deliberate: two dbt builds racing on one schema is not a thing to discover in production |
| exit `70` | read the output. The script names which step failed and leaves the others' results visible |
| green execution but nothing happened | the Code node was removed or bypassed. See the note in section 6 |
| the pipeline failed but no Telegram message arrived | one of the two traps below |

### Testing the alert, and the two traps that make it look broken

Both cost time on 2026-09-13, and both will cost it again.

**An error workflow never fires on a manual execution.** n8n only calls it for
*production* executions — the ones started by the trigger. So the obvious way to
test an alert is the one way that cannot work. To test it for real: set the
Schedule Trigger to `Minutes / 1`, **activate** the workflow, and wait. Then put
the schedule back.

> Changing only the *hour* of a `Weeks / Monday` rule does not make it fire
> today. It is the **Trigger Interval** field that has to change.

**`On Error` must stay on *Stop Workflow*** on the Code node. Set to *Continue
(using error output)*, the error goes down a branch and **the execution finishes
as a success** — so n8n has nothing to report and never calls the error
workflow. The node shows something red while the execution is green. Check the
status in the *Executions* list, not the colour of the node.

A good failure to test with is `refreshh`: the server refuses the word before
opening any connection, so nothing is ingested and the test can be replayed as
often as needed. Expect exit `64`, and a Telegram message quoting
`the task name was refused by the whitelist`.

Nothing here ever touches `root-n8n-1`, `root-n8n-worker-1`, `n8n-postgres`,
`redis` or `root-traefik-1`. `deploy-vps.sh` ends by listing the containers, so
the proof that they are still running is in the output rather than in a promise.
