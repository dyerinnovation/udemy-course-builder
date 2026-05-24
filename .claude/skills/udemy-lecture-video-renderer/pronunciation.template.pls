<?xml version="1.0" encoding="UTF-8"?>
<!--
  Universal tech-term pronunciation lexicon (template / fallback).

  CRITICAL: this file uses <alias> rules (literal text substitution at TTS
  preprocessing time). Do NOT switch to <phoneme> rules — eleven_multilingual_v2
  (the model this skill uses) silently IGNORES phoneme rules. See playbook.md
  "ElevenLabs pronunciation rule types — alias vs phoneme model support".

  Each course can override or extend this file via:
    <course_root>/course-metadata/pronunciation.pls
  Course entries win on grapheme conflict (see tts_render.py::_resolve_pronunciation_dict).

  Adding a new term: pick the PHONETIC English spelling that produces the
  sound you want when the model reads the alias literally.
    - Letter-by-letter acronyms: use phonetic letters as words.
      Right: "ay pee eye"   Wrong: "A P I" (gets mumbled together)
    - Word-like acronyms (JSON, YAML, SQL, RAG): use common pronunciation.
  This matches the ElevenLabs cookbook guidance for alias rules:
  https://elevenlabs.io/docs/eleven-api/guides/how-to/text-to-speech/pronunciation-dictionaries

  The merged dict is auto-uploaded once per unique content hash and cached at
  <course_root>/course-metadata/tts-config.json.
-->

<lexicon version="1.0" xmlns="http://www.w3.org/2005/01/pronunciation-lexicon" xml:lang="en-US">

  <!-- Acronyms read letter-by-letter (phonetic English spelling) -->
  <lexeme><grapheme>API</grapheme><alias>A. P. I.</alias></lexeme>
  <lexeme><grapheme>APIs</grapheme><alias>A. P. I.s</alias></lexeme>
  <lexeme><grapheme>SDK</grapheme><alias>ess dee kay</alias></lexeme>
  <lexeme><grapheme>SDKs</grapheme><alias>ess dee kays</alias></lexeme>
  <lexeme><grapheme>CLI</grapheme><alias>see ell eye</alias></lexeme>
  <lexeme><grapheme>CLIs</grapheme><alias>see ell eyes</alias></lexeme>
  <lexeme><grapheme>MCP</grapheme><alias>em see pee</alias></lexeme>
  <lexeme><grapheme>SSML</grapheme><alias>ess ess em ell</alias></lexeme>
  <lexeme><grapheme>LLM</grapheme><alias>ell ell em</alias></lexeme>
  <lexeme><grapheme>LLMs</grapheme><alias>ell ell ems</alias></lexeme>
  <lexeme><grapheme>HTTP</grapheme><alias>aitch tee tee pee</alias></lexeme>
  <lexeme><grapheme>HTTPS</grapheme><alias>aitch tee tee pee ess</alias></lexeme>
  <lexeme><grapheme>URL</grapheme><alias>you are ell</alias></lexeme>
  <lexeme><grapheme>URLs</grapheme><alias>you are ells</alias></lexeme>
  <lexeme><grapheme>UUID</grapheme><alias>you you eye dee</alias></lexeme>

  <!-- Word-like acronyms read as words -->
  <lexeme><grapheme>JSON</grapheme><alias>jay-sahn</alias></lexeme>
  <lexeme><grapheme>YAML</grapheme><alias>yamel</alias></lexeme>
  <lexeme><grapheme>SQL</grapheme><alias>sequel</alias></lexeme>
  <lexeme><grapheme>RAG</grapheme><alias>rag</alias></lexeme>
  <lexeme><grapheme>regex</grapheme><alias>rej-eks</alias></lexeme>

</lexicon>
