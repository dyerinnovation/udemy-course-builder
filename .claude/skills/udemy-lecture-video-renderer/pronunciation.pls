<?xml version="1.0" encoding="UTF-8"?>
<!--
  Pronunciation Lexicon Specification (PLS) for the CCA Udemy Course
  Format: W3C PLS 1.0 (https://www.w3.org/TR/pronunciation-lexicon/)

  Upload this file to ElevenLabs once to create a pronunciation dictionary:

    curl -X POST https://api.elevenlabs.io/v1/pronunciation-dictionaries/add-from-file \
      -H "xi-api-key: $ELEVENLABS_API_KEY" \
      -F "file=@pronunciation.pls;type=application/pls+xml" \
      -F "name=CCA Course Lexicon"

  The response JSON includes:
    "id"         → set as ELEVENLABS_PRONUNCIATION_DICT_ID in .env
    "version_id" → set as ELEVENLABS_PRONUNCIATION_DICT_VERSION in .env

  ElevenLabs docs: https://elevenlabs.io/docs/eleven-api/guides/cookbooks/text-to-speech/pronunciation-dictionaries

  Alphabet note: ElevenLabs supports IPA phonemes (alphabet="ipa") in PLS files.
  Arpabet is NOT supported natively; use IPA transcriptions instead.

  IPA reference used below follows standard American English conventions.
  Test each entry with a single-slide render after uploading.
-->

<lexicon version="1.0"
         xmlns="http://www.w3.org/2005/01/pronunciation-lexicon"
         alphabet="ipa"
         xml:lang="en-US">

  <!-- =====================================================================
       Brand names
       ===================================================================== -->

  <!-- Anthropic: stress on second syllable — an-THROP-ic -->
  <lexeme>
    <grapheme>Anthropic</grapheme>
    <phoneme>ænˈθrɒpɪk</phoneme>
  </lexeme>

  <!-- Claude: single syllable, rhymes with "clawed" -->
  <lexeme>
    <grapheme>Claude</grapheme>
    <phoneme>klɔːd</phoneme>
  </lexeme>

  <!-- Sonnet: two syllables, SON-it -->
  <lexeme>
    <grapheme>Sonnet</grapheme>
    <phoneme>ˈsɒnɪt</phoneme>
  </lexeme>

  <!-- Opus: two syllables, OH-pus -->
  <lexeme>
    <grapheme>Opus</grapheme>
    <phoneme>ˈoʊpəs</phoneme>
  </lexeme>

  <!-- Haiku: two syllables, HY-koo -->
  <lexeme>
    <grapheme>Haiku</grapheme>
    <phoneme>ˈhaɪkuː</phoneme>
  </lexeme>

  <!-- =====================================================================
       Acronyms — spelled out as letters
       ===================================================================== -->

  <!-- API: AY-PEE-EYE -->
  <lexeme>
    <grapheme>API</grapheme>
    <phoneme>ˌeɪ piː ˈaɪ</phoneme>
  </lexeme>

  <!-- APIs: AY-PEE-EYES -->
  <lexeme>
    <grapheme>APIs</grapheme>
    <phoneme>ˌeɪ piː ˈaɪz</phoneme>
  </lexeme>

  <!-- SDK: ESS-DEE-KAY -->
  <lexeme>
    <grapheme>SDK</grapheme>
    <phoneme>ˌɛs diː ˈkeɪ</phoneme>
  </lexeme>

  <!-- SDKs: ESS-DEE-KAYZ -->
  <lexeme>
    <grapheme>SDKs</grapheme>
    <phoneme>ˌɛs diː ˈkeɪz</phoneme>
  </lexeme>

  <!-- MCP: EM-SEE-PEE -->
  <lexeme>
    <grapheme>MCP</grapheme>
    <phoneme>ˌɛm siː ˈpiː</phoneme>
  </lexeme>

  <!-- CLI: SEE-ELL-EYE -->
  <lexeme>
    <grapheme>CLI</grapheme>
    <phoneme>ˌsiː ɛl ˈaɪ</phoneme>
  </lexeme>

  <!-- CLIs: SEE-ELL-EYES -->
  <lexeme>
    <grapheme>CLIs</grapheme>
    <phoneme>ˌsiː ɛl ˈaɪz</phoneme>
  </lexeme>

  <!-- SSML: ESS-ESS-EM-ELL -->
  <lexeme>
    <grapheme>SSML</grapheme>
    <phoneme>ˌɛs ɛs ɛm ˈɛl</phoneme>
  </lexeme>

  <!-- RAG: spell out — AHR-AY-JEE (not "rag" the word) -->
  <lexeme>
    <grapheme>RAG</grapheme>
    <phoneme>ˌɑːr eɪ ˈdʒiː</phoneme>
  </lexeme>

  <!-- LLM: ELL-ELL-EM -->
  <lexeme>
    <grapheme>LLM</grapheme>
    <phoneme>ˌɛl ɛl ˈɛm</phoneme>
  </lexeme>

  <!-- LLMs: ELL-ELL-EMZ -->
  <lexeme>
    <grapheme>LLMs</grapheme>
    <phoneme>ˌɛl ɛl ˈɛmz</phoneme>
  </lexeme>

  <!-- =====================================================================
       Common tech terms that may be mispronounced
       ===================================================================== -->

  <!-- JSON: JAY-son (not "jay-es-oh-en") -->
  <lexeme>
    <grapheme>JSON</grapheme>
    <phoneme>ˈdʒeɪsən</phoneme>
  </lexeme>

  <!-- CCA: SEE-SEE-AY (abbreviation for Claude Certified Architect) -->
  <lexeme>
    <grapheme>CCA</grapheme>
    <phoneme>ˌsiː siː ˈeɪ</phoneme>
  </lexeme>

  <!-- CCA-F: SEE-SEE-AY-EFF -->
  <lexeme>
    <grapheme>CCA-F</grapheme>
    <phoneme>ˌsiː siː eɪ ˈɛf</phoneme>
  </lexeme>

</lexicon>
