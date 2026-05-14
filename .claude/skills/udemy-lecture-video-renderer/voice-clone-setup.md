# ElevenLabs Voice Clone Setup — One-Time Per-User

This walkthrough gets your cloned ElevenLabs voice wired into the
`udemy-lecture-video-renderer` skill. Once done, the same voice + API key
narrate **every future Udemy course** built with this plugin — you don't
repeat this for each course.

**Time:** ~15 min recording + ~10 min UI + `.env` wiring.
**End state:** `.env` populated with `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID`.

---

## Tier Decision (Read This First)

Free and Starter tiers add a watermark to generated audio **and strip
commercial rights**. Neither is usable for a paid Udemy course.

| Tier | Price | Credits/mo | Lectures/mo (est.) | Commercial rights |
|---|---|---|---|---|
| Free | $0 | 10k | ~1 | No |
| Starter | $5 | 30k | ~3 | No |
| Creator | $22 | 121k | ~14 | Yes |
| **Pro** | **$99** | **500k** | **~55** | **Yes** |
| Scale | $330 | 2M | ~220 | Yes |

**Recommendation:** subscribe to **Pro ($99/mo)** for 1–2 months. Average
lecture is ~5,000 credits; Pro covers ~55 lectures per cycle. **Downgrade
immediately after each course's audio is rendered.**

> Pricing reference: https://elevenlabs.io/pricing

---

## Hardware Checklist

Before recording:

- **USB condenser microphone** — Shure MV7, Blue Yeti, Rode NT-USB, AT2020USB+ all work well
- **Pop filter** — reduces plosives on "p" and "b" sounds
- **Quiet room** — close windows, disable HVAC, shut laptop vents
- **Silence check** — record 5 seconds of silence and listen back; any hum or hiss degrades the clone

> **Warning:** Do NOT record on a phone mic, laptop built-in mic, or AirPods.
> Clone quality scales directly with sample quality. A poor sample produces
> a poor clone that cannot be improved without re-recording.

---

## Recording the Clone Sample

**Target:** 1–2 minutes of continuous speech. The default script below is
~280 words (~90 seconds at a comfortable narration pace) and seeds common
tech-course terminology (Anthropic, Claude, MCP, JSON, SDK, API, CLI,
agent, structured output, batch, citation, retrieval, prompt caching).

If your future courses cover different domains (data science, cloud,
security, etc.), feel free to substitute terms — the clone learns **vocal
texture** more than specific words, so the exact term list barely matters.
What matters is range, pacing, and clean audio.

Set your recorder to **44.1 kHz / 128 kbps minimum** (Audacity,
GarageBand, or QuickTime all work). Save as:

```
~/Downloads/voice-clone-sample.mp3
```

**Read this script aloud — warm, confident, instructor tone:**

---

> Welcome to the course. Over the next several hours we're going to move
> from the fundamentals of the Anthropic API all the way through advanced
> topics like multi-agent orchestration, observability, and
> production-grade deployment.
>
> Let's start with the basics. Anthropic offers three model families:
> Claude Opus, Claude Sonnet, and Claude Haiku. Each sits at a different
> point on the capability-cost-speed curve, and choosing the right one for
> a given task is one of the first decisions you'll make as an architect.
>
> The SDK is available in Python and TypeScript. You'll authenticate with
> an API key, call the Messages endpoint, and get back a structured
> response that includes a stop reason — either "end_turn," "tool_use," or
> "max_tokens." Knowing which stop reason fired is how you branch your
> agent's logic.
>
> Tool use is the mechanism that lets Claude interact with the outside
> world. You define a JSON schema for each tool, pass it in the request,
> and Claude returns a structured tool call your application executes.
> Combine that with prompt caching and you have the foundation of an
> efficient agentic loop.
>
> The Model Context Protocol — MCP — takes this further. It's a
> standardized interface that lets Claude connect to external services,
> databases, and file systems through a defined client-server handshake.
>
> We'll also cover structured output, citation, retrieval, batch
> processing, and the CLI. By the end, you'll understand not just how to
> call the Claude API, but how to design systems around it — systems that
> are observable, maintainable, and ready for production.
>
> Let's get started.

---

Read at a natural teaching pace. Do not rush. One clean take is enough.

---

## Web UI Walkthrough

1. **Go to** https://elevenlabs.io — log in or create an account (use the Pro plan)
2. **Left sidebar** → click **Voices**
3. **Click the `+` button** → select **Instant Voice Clone**
4. **Upload** `~/Downloads/voice-clone-sample.mp3`
5. **Name the voice:** `[Your Name] — Narration` (e.g. `Jonathan Dyer — Narration`)
6. **Tick the consent / IP-rights checkbox** (confirms you own the voice sample)
7. **Click Save**
8. **Wait ~30 seconds** — ElevenLabs processes the sample. The voice card appears when ready.

---

## Retrieve the Voice ID

After the voice card appears:

1. **Click the voice card** to open it
2. Look at the browser URL — it contains `/voice-lab/<voice_id>`. **Copy the `<voice_id>` hash** (looks like `21m00Tcm4TlvDq8ikWAM`)

Alternatively, list all voices via API:

```bash
curl -X GET "https://api.elevenlabs.io/v1/voices" \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  | python3 -m json.tool
```

---

## Create the API Key

1. **Top-right avatar** → **API Keys**
2. **Click Create API Key** → name it `Udemy Course Builder`
3. **Copy the key immediately** — shown **once only**

> **Security:**
> - Never paste the full key into chat
> - Never commit it to git
> - Store only in `.env` (which is gitignored at the skill level)

---

## Wire Up `.env`

Open (or create) this file — it lives **in the plugin**, not in any
individual course repo, because it's a one-time per-user setting:

```
~/Documents/dev/udemy-courses/udemy-course-builder/.claude/skills/udemy-lecture-video-renderer/.env
```

Paste in:

```env
ELEVENLABS_API_KEY=<paste your key here>
ELEVENLABS_VOICE_ID=<paste your voice_id here>
```

> **Note:** Earlier versions of this skill required additional env vars
> for the pronunciation dictionary. Those are now **auto-managed
> per-course** — see "Per-Course Pronunciation Dictionary" below.

---

## Per-Course Pronunciation Dictionary

Each course can include its own pronunciation overrides for jargon
specific to that course's domain. The skill auto-merges the universal
template (in this skill's `pronunciation.template.pls`) with a per-course
override at:

```
<course_root>/course-metadata/pronunciation.pls
```

If the course PLS doesn't exist, the universal template is used as-is.

**To add course-specific pronunciations** (for any new course):

1. Create `<course_root>/course-metadata/pronunciation.pls` with the same
   PLS 1.0 / IPA format as the skill template
2. Add `<lexeme>` entries for course-specific terms (product names,
   technical acronyms, etc.) — entries override the universal template
   on grapheme conflict
3. Run the renderer — first run auto-uploads the merged dictionary to
   ElevenLabs and caches the ID at
   `<course_root>/course-metadata/tts-config.json`
4. Subsequent runs reuse the cached dictionary; the skill re-uploads
   automatically if you edit the PLS (cache key is the SHA-256 of the
   merged content)

Both `pronunciation.pls` and `tts-config.json` are course-repo files and
should be **committed to git** — the audit trail of pronunciations is
useful, and `tts-config.json` makes the upload-once contract reproducible.

---

## Smoke-Test Handshake

When you're ready to test, tell Claude:

- The **voice name** you set (e.g., `Jonathan Dyer — Narration`)
- The **last 4 characters** of your voice_id (e.g., `ending in ...WAM`)
- Confirmation that `.env` is populated with both values

> **Do NOT paste the full API key or full voice_id into chat.** The
> last-4-chars convention is enough for Claude to verify the ID matches.

Claude will then run the smoke test on one lecture, render a short test
clip for your approval, and (on approval) batch-render the rest of the
course.

---

## Troubleshooting

- **"Voice doesn't sound like me"** — re-record with more sentence variety, less room reverb, and a longer sample (aim for 90–120 seconds). The clone mirrors whatever it receives.
- **"Pronunciation is off for technical terms"** — that's normal on the first slide. The skill auto-installs a pronunciation dictionary; if a specific term is still wrong, add it to the per-course `pronunciation.pls`.
- **"Instant Voice Clone option is locked / greyed out"** — you're on Free or Starter tier. Upgrade to Creator or Pro; the option unlocks immediately.
- **"API returns 401 Unauthorized"** — check for: leading/trailing spaces in the `.env` value, accidental quote characters around the key, or wrong variable name (`ELEVENLABS_API_KEY` exactly, no typos).
- **"Credits exhausted mid-batch"** — Pro gives 500k/mo; if you hit the limit, wait for monthly reset or temporarily upgrade to Scale for one month.
