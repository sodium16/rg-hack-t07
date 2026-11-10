# Azure setup — TEMPORARY working notes

**Temporary document.** Not a deliverable, not part of the submission. Fold the useful parts into `README.md` before zipping the code, then delete this file.

Goal: a working `rg-hack-T##` with a Speech resource, one Foundry chat deployment, a budget alert, and content filtering — plus the four env values the app needs. Allow **20–30 minutes**. Do every step in this order: the budget alert goes on before any billable resource.

Team number is `T##` below; replace it with your real number everywhere.

---

## 0. Before you start

- [x] You can sign in to the Azure portal with permission to create resource groups and budgets (a student/free subscription is fine).
- [x] You know the team's real `T##`.
- [x] You have a terminal (Git Bash on this machine) for the connectivity checks.
- [x] Nothing secret is on screen if you are recording: the portal's **Keys** blade, subscription ID, and `.env` stay out of screenshots and video.

Hard rule from the handout: a visible key costs 5 points. A key is only ever pasted into a local `.env` (gitignored), never into chat, code, docs, or a screenshot.

---

## 1. Resource group

Portal → **Resource groups** → **Create**

| Field | Value |
|---|---|
| Subscription | the team's subscription |
| Resource group | `rg-hack-T##` |
| Region | pick the region you will use for resources (see §2) |

Create, then open the group. Every resource below must land in this group — it is the thing you delete at the end and screenshot for `3_Azure_Proof.pdf`.

## 2. Choose one region (do this before creating anything)

Two constraints must both hold in the same region:

1. **Azure AI Speech supports fast transcription** there.
2. **The Foundry chat model you want has quota** there.

Check Microsoft Learn's *Speech service regions* table for fast transcription support, and the Foundry portal's model catalogue for quota. India regions frequently do **not** list fast transcription; if neither does, choose the nearest supported region and use it consistently — do not split Speech and Foundry across regions unless you must (it complicates nothing technically, but two regions means two sets of screenshots).

The roadmap's G0 gate is exactly this: if fast transcription is unavailable, switch region **now**, before writing Speech code.

## 3. Budget alert (before any billable resource)

Portal → **Cost Management + Billing** → **Budgets** → **Add**

- Scope: the subscription (or `rg-hack-T##` if budgets must be scoped to a group).
- Amount: small and deliberate — e.g. **USD 10** equivalent.
- Alerts: 50%, 80%, 100% actual (and optionally a forecasted alert), sent to a team mailbox that someone actually reads.
- Screenshot the budget with the amount and alert thresholds visible. This screenshot is required in `3_Azure_Proof.pdf`.

If budget creation is blocked by permissions, stop and fix that with the subscription owner before spending anything. Do not proceed and "add it later".

## 4. Azure AI Speech resource

Portal → **Create a resource** → search **Speech** → **Create**

| Field | Value |
|---|---|
| Resource group | `rg-hack-T##` |
| Region | the region from §2 |
| Name | e.g. `speech-T##` |
| Pricing tier | **F0** if offered for the region, else **S0** |

Notes:
- F0 is free but rate-limited; if fast transcription rejects the tier, switch to S0 (a day of use costs roughly the price of a coffee — check the current pricing page for your region).
- Do **not** enable text-to-speech, custom speech, or anything else. The app only calls transcription.

Then **Keys and Endpoint**: copy **KEY 1** and note the **Location/Region**. Paste them into your local `.env` (see §8) — never into the repo.

## 5. Foundry project and chat deployment

1. Open **https://ai.azure.com** and sign in.
2. **Create project** → name e.g. `p11-lecture-notes` → select **existing** resource group `rg-hack-T##` → the region from §2.
3. In the project, open **Models + endpoints** (or **Deployments**) → **Deploy model** → choose a small, current chat model that supports **structured outputs / JSON mode**. `gpt-4o-mini`-class or a newer small model is enough; do not deploy a large model "just in case".
4. Deployment name: keep it simple and stable, e.g. `chat`. This exact string is `AZURE_FOUNDRY_DEPLOYMENT` — it is a *deployment* name, not the model family name, and is the single most common source of 404s.
5. Copy the endpoint and key from the project/resource **Keys and Endpoint** blade, and take the `api-version` from the portal's sample code (it is newer than any value written in these docs).

Two endpoint shapes exist; use exactly what the portal shows you:

- Azure OpenAI-style: `https://<resource>.openai.azure.com/`
- Foundry/AI Services-style: `https://<resource>.services.ai.azure.com/`

Record in a shared team note (not the key): resource name, region, deployment name, model name, api-version.

## 6. Content filter — leave it on

Foundry portal → project → **Guardrails and controls** (older UI: **Content filters**) → confirm the **default** filter is attached to the deployment.

- Keep it on. Do not disable it, and do not raise thresholds to make a demo answer appear.
- Screenshot the filter configuration showing the categories and severity thresholds. Required in `3_Azure_Proof.pdf`.
- The app must catch `finish_reason == "content_filter"` and show a friendly message (Phase 3/4 work, not yours now).

## 7. Prove both services answer (before handing over)

Put the values in your shell. In Git Bash from the repo root:

```bash
set -a; . ./.env; set +a   # loads the local .env into this shell
```

If your `.env` has Windows CRLF line endings this can fail with `$'\r'` errors; run `dos2unix .env` or create the file in an editor set to LF.

**Speech** — replace the sample path with any 5–10 second clip (m4a/wav/mp3):

```bash
curl -sS -X POST \
  "https://${AZURE_SPEECH_REGION}.api.cognitive.microsoft.com/speechtotext/transcriptions:transcribe?api-version=2025-10-15" \
  -H "Ocp-Apim-Subscription-Key: ${AZURE_SPEECH_KEY}" \
  -F "audio=@sample.wav" \
  -F 'definition={"locales":["en-US"]}' | head -c 800
```

Expect JSON containing `durationMilliseconds` and `phrases[]`. A 401 means the key belongs to another resource; a 404 on `api-version` means the region does not run fast transcription (return to §2).

**Foundry chat:**

```bash
curl -sS \
  "${AZURE_FOUNDRY_ENDPOINT}openai/deployments/${AZURE_FOUNDRY_DEPLOYMENT}/chat/completions?api-version=${AZURE_FOUNDRY_API_VERSION}" \
  -H "Content-Type: application/json" \
  -H "api-key: ${AZURE_FOUNDRY_KEY}" \
  -d '{"messages":[{"role":"user","content":"Reply with the single word OK"}],"max_tokens":5}' | head -c 600
```

Expect a normal completion. `DeploymentNotFound` → the deployment name is wrong. If your endpoint already ends in `/openai/v1`, use `"${AZURE_FOUNDRY_ENDPOINT}chat/completions"` with `Authorization: Bearer ${AZURE_FOUNDRY_KEY}` instead.

Do not paste the output of either command into a public channel if it contains request IDs; the transcript text is fine.

## 8. Local `.env` (never committed)

Create `.env` in the repo root (it is gitignored). `.env.example` stays with empty values.

```
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=
AZURE_SPEECH_LOCALE=en-US
AZURE_FOUNDRY_ENDPOINT=
AZURE_FOUNDRY_KEY=
AZURE_FOUNDRY_DEPLOYMENT=
AZURE_FOUNDRY_API_VERSION=
MAX_AUDIO_MINUTES=10
MATCH_THRESHOLD=0.88
```

Rules that matter for scoring:

- Never `git add .env`. Confirm with `git status --porcelain` before every commit.
- Never screenshot the Keys blade, the budget's subscription ID, or a terminal running `env`.
- If a key appears anywhere public, rotate it immediately in the portal (Regenerate) and tell the team.

## 9. Screenshot checklist → `3_Azure_Proof.pdf`

Capture these now, while you are in the right blades; retaking them later costs time you will not have:

- [ ] Resource group `rg-hack-T##` overview (subscription ID hidden/cropped)
- [ ] Budget with amount + alert thresholds
- [ ] Speech resource overview (no keys visible)
- [ ] Foundry project / each model deployment
- [ ] Content filter configuration
- [ ] (optional) one successful transcription response, with no key header visible

## 10. Hand-off to the build

Give the team, in a note (never the key values):

| Value | Where it goes |
|---|---|
| Speech region | `AZURE_SPEECH_REGION` |
| Speech key | `AZURE_SPEECH_KEY` (local `.env` only) |
| Foundry endpoint | `AZURE_FOUNDRY_ENDPOINT` |
| Foundry key | `AZURE_FOUNDRY_KEY` (local `.env` only) |
| Deployment name | `AZURE_FOUNDRY_DEPLOYMENT` |
| api-version from portal | `AZURE_FOUNDRY_API_VERSION` |
| Locale | `AZURE_SPEECH_LOCALE` (default `en-US`) |

The first build milestone (transcript index + verification engine) needs **none** of these — it runs offline on a fixture. So if a key or quota is still pending, the team is not blocked.

---

## 11. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| 401 from Speech | key from a different resource, or wrong region in the URL | re-copy KEY 1 from the Speech resource; region must match the resource |
| 404 on `transcriptions:transcribe` | region without fast transcription, or wrong api-version | check the region table; use `2025-10-15` on a supported region |
| 400 unsupported audio | container/codec not accepted | convert to 16 kHz mono WAV with ffmpeg |
| `DeploymentNotFound` | deployment name ≠ model name | use the name shown under Deployments |
| 429 / quota errors | TPM exhausted or quota 0 | wait, or deploy a smaller model in a region with quota |
| `Model not found` on deploy | model unavailable in region | pick another model or region; record which |
| Budget alert not firing | alert scoped to a different subscription | verify scope and email recipient in Cost Management |
| Curl fails with `$'\r'` | CRLF in `.env` | convert to LF |

## 12. Teardown (after results are captured)

Delete `rg-hack-T##` once A1/A2/A3 evidence, screenshots and the video are captured. The handout requires it, and it is the final defence against a surprise bill. Keep the screenshots — they are the evidence.

---

## What NOT to create

Text-to-speech, vision, Document Intelligence, Azure AI Search, an agent with threads, a database, or a web app deployment. The build needs exactly two Azure services: Speech transcription and one Foundry chat deployment. Every extra resource is cost, screenshot work, and scope the judges did not ask for.
