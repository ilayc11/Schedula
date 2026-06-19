"""
Language Detection and Translation Module

Handles detection of Hebrew language and translation to English for the constraint processing pipeline.
Uses langdetect for language detection and deep-translator (Google Translate) for translation.
"""

from typing import Dict, Any, Tuple, Optional
from langdetect import detect, DetectorFactory
from deep_translator import GoogleTranslator

# Set seed for consistent language detection results
DetectorFactory.seed = 0


class LanguageTranslator:
    """
    Handles language detection and translation for the LLM pipeline.
    
    Supports:
    - Automatic language detection
    - Hebrew to English translation
    - Metadata tracking for translation operations
    """
    
    def __init__(self):
        """Initialize the language translator with Google Translate backend."""
        self.translator = GoogleTranslator(source='auto', target='en')
        self.supported_languages = {'en', 'he'}  # English and Hebrew
        
        # Language code mapping: langdetect -> Google Translate
        # langdetect uses ISO 639-1 codes, but Google Translate may use different codes
        self.lang_code_mapping = {
            'he': 'iw',  # Hebrew: langdetect returns 'he', Google Translate expects 'iw'
        }
    
    def detect_language(self, text: str) -> str:
        """
        Detect the language of the input text.
        
        Args:
            text: Input text to detect language from
            
        Returns:
            Language code (e.g., 'en', 'he')
            
        Raises:
            Exception: If language detection fails
        """
        try:
            # langdetect returns ISO 639-1 language codes
            language = detect(text)
            print(f"🌍 Detected language: {language}")
            return language
        except Exception as e:
            print(f"⚠️  Language detection failed: {e}. Defaulting to English.")
            return 'en'  # Default to English if detection fails
    
    def translate_to_english(self, text: str, source_language: str) -> Tuple[str, Dict[str, Any]]:
        """
        Translate text from source language to English.
        
        Args:
            text: Text to translate
            source_language: Source language code (e.g., 'he' for Hebrew)
            
        Returns:
            Tuple of (translated_text, translation_metadata)
            
        Raises:
            Exception: If translation fails
        """
        try:
            print(f"🔄 Translating from {source_language} to English...")
            
            # Map language code for Google Translate compatibility
            # langdetect uses 'he' for Hebrew, but Google Translate uses 'iw'
            google_lang_code = self.lang_code_mapping.get(source_language, source_language)
            
            if google_lang_code != source_language:
                print(f"   Mapped language code: {source_language} → {google_lang_code}")
            
            # Create a translator with the specific source language
            translator = GoogleTranslator(source=google_lang_code, target='en')
            translated_text = translator.translate(text)
            
            metadata = {
                "translation_performed": True,
                "source_language": source_language,
                "google_language_code": google_lang_code,
                "target_language": "en",
                "original_text": text,
                "translator": "google_translate",
                "translation_success": True
            }
            
            print(f"✅ Translation successful")
            print(f"   Original ({source_language}): {text[:100]}..." if len(text) > 100 else f"   Original ({source_language}): {text}")
            print(f"   Translated (en): {translated_text[:100]}..." if len(translated_text) > 100 else f"   Translated (en): {translated_text}")
            
            return translated_text, metadata
            
        except Exception as e:
            error_msg = f"Translation failed: {str(e)}"
            print(f"❌ {error_msg}")
            
            metadata = {
                "translation_performed": True,
                "source_language": source_language,
                "target_language": "en",
                "original_text": text,
                "translator": "google_translate",
                "translation_success": False,
                "translation_error": error_msg
            }
            
            # Return original text if translation fails
            return text, metadata
    
    def process_text(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """
        Process input text: detect language and translate if needed.
        
        This is the main entry point for language processing.
        
        Args:
            text: Input text to process
            
        Returns:
            Tuple of (processed_text, language_metadata)
            - processed_text: English text ready for pipeline
            - language_metadata: Information about language detection/translation
        """
        # Detect language
        try:
            detected_language = self.detect_language(text)
        except Exception as e:
            print(f"⚠️  Language detection error: {e}. Assuming English.")
            detected_language = 'en'
        
        # If English, no translation needed
        if detected_language == 'en':
            metadata = {
                "translation_performed": False,
                "detected_language": "en",
                "original_text": text
            }
            return text, metadata
        
        # If Hebrew, translate to English
        if detected_language == 'he':
            translated_text, translation_metadata = self.translate_to_english(text, 'he')
            return translated_text, translation_metadata
        
        # For other languages, attempt translation but warn user
        print(f"⚠️  Unsupported language detected: {detected_language}")
        print(f"⚠️  Attempting translation to English, but results may vary")
        
        try:
            translated_text, translation_metadata = self.translate_to_english(text, detected_language)
            translation_metadata["warning"] = f"Unsupported language '{detected_language}' - translation may be inaccurate"
            return translated_text, translation_metadata
        except Exception as e:
            print(f"❌ Translation failed for unsupported language: {e}")
            print(f"⚠️  Proceeding with original text - pipeline may fail")
            
            metadata = {
                "translation_performed": False,
                "detected_language": detected_language,
                "original_text": text,
                "error": f"Translation failed: {str(e)}",
                "warning": "Proceeding with non-English text - pipeline may fail"
            }
            return text, metadata


# Singleton instance for reuse
_translator_instance: Optional[LanguageTranslator] = None


def get_language_translator() -> LanguageTranslator:
    """
    Get or create the language translator instance.
    Uses singleton pattern for efficiency.
    """
    global _translator_instance
    
    if _translator_instance is None:
        _translator_instance = LanguageTranslator()
    
    return _translator_instance