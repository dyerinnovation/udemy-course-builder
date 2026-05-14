<?xml version="1.0" encoding="UTF-8"?>
<!--
  Pronunciation Lexicon Specification (PLS) — Universal Tech Course Template

  This file is the skill-level FALLBACK lexicon. It contains pronunciations
  for terms that apply to any tech/AI/dev course (acronyms spelled as
  letters, JSON, etc.). It is intentionally course-agnostic.

  Per-course overrides:
    Each course may add its OWN PLS at:
      <course_root>/course-metadata/pronunciation.pls

    At render time, tts_render.py merges this template with the course
    override (course entries win on grapheme conflict), uploads the
    combined dictionary to ElevenLabs, and caches the returned
    pronunciation_dictionary_id + version_id in:
      <course_root>/course-metadata/tts-config.json

    The cache is keyed on a SHA-256 hash of the merged PLS content; the
    skill re-uploads automatically when either this template or the
    per-course PLS changes.

  Format: W3C PLS 1.0 (https://www.w3.org/TR/pronunciation-lexicon/)
  Alphabet: ElevenLabs supports IPA. Arpabet is NOT supported.
  Reference: https://elevenlabs.io/docs/eleven-api/guides/cookbooks/text-to-speech/pronunciation-dictionaries
-->

<lexicon version="1.0"
         xmlns="http://www.w3.org/2005/01/pronunciation-lexicon"
         alphabet="ipa"
         xml:lang="en-US">

  <!-- =====================================================================
       Acronyms — spelled out as letters (universal across tech courses)
       ===================================================================== -->

  <lexeme>
    <grapheme>API</grapheme>
    <phoneme>ˌeɪ piː ˈaɪ</phoneme>
  </lexeme>
  <lexeme>
    <grapheme>APIs</grapheme>
    <phoneme>ˌeɪ piː ˈaɪz</phoneme>
  </lexeme>

  <lexeme>
    <grapheme>SDK</grapheme>
    <phoneme>ˌɛs diː ˈkeɪ</phoneme>
  </lexeme>
  <lexeme>
    <grapheme>SDKs</grapheme>
    <phoneme>ˌɛs diː ˈkeɪz</phoneme>
  </lexeme>

  <lexeme>
    <grapheme>CLI</grapheme>
    <phoneme>ˌsiː ɛl ˈaɪ</phoneme>
  </lexeme>
  <lexeme>
    <grapheme>CLIs</grapheme>
    <phoneme>ˌsiː ɛl ˈaɪz</phoneme>
  </lexeme>

  <lexeme>
    <grapheme>LLM</grapheme>
    <phoneme>ˌɛl ɛl ˈɛm</phoneme>
  </lexeme>
  <lexeme>
    <grapheme>LLMs</grapheme>
    <phoneme>ˌɛl ɛl ˈɛmz</phoneme>
  </lexeme>

  <lexeme>
    <grapheme>SSML</grapheme>
    <phoneme>ˌɛs ɛs ɛm ˈɛl</phoneme>
  </lexeme>

  <!-- RAG: spelled out (not the word "rag") -->
  <lexeme>
    <grapheme>RAG</grapheme>
    <phoneme>ˌɑːr eɪ ˈdʒiː</phoneme>
  </lexeme>

  <lexeme>
    <grapheme>HTTP</grapheme>
    <phoneme>ˌeɪtʃ tiː tiː ˈpiː</phoneme>
  </lexeme>
  <lexeme>
    <grapheme>HTTPS</grapheme>
    <phoneme>ˌeɪtʃ tiː tiː piː ˈɛs</phoneme>
  </lexeme>

  <lexeme>
    <grapheme>URL</grapheme>
    <phoneme>ˌjuː ɑːr ˈɛl</phoneme>
  </lexeme>
  <lexeme>
    <grapheme>URLs</grapheme>
    <phoneme>ˌjuː ɑːr ˈɛlz</phoneme>
  </lexeme>

  <lexeme>
    <grapheme>UUID</grapheme>
    <phoneme>ˌjuː juː aɪ ˈdiː</phoneme>
  </lexeme>

  <!-- =====================================================================
       Common tech terms that are often mispronounced
       ===================================================================== -->

  <!-- JSON: "JAY-son" not "jay-es-oh-en" -->
  <lexeme>
    <grapheme>JSON</grapheme>
    <phoneme>ˈdʒeɪsən</phoneme>
  </lexeme>

  <!-- YAML: "YAM-ul" -->
  <lexeme>
    <grapheme>YAML</grapheme>
    <phoneme>ˈjæməl</phoneme>
  </lexeme>

  <!-- SQL: "sequel" (most common in spoken English) -->
  <lexeme>
    <grapheme>SQL</grapheme>
    <phoneme>ˈsiːkwəl</phoneme>
  </lexeme>

  <!-- regex: "REJ-eks" -->
  <lexeme>
    <grapheme>regex</grapheme>
    <phoneme>ˈrɛdʒɛks</phoneme>
  </lexeme>

</lexicon>
