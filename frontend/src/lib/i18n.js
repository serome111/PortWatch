import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import en from '../locales/en.json';
import es from '../locales/es.json';
import narrativesEn from '../locales/narratives_en.json';
import narrativesEs from '../locales/narratives_es.json';

i18n
    .use(LanguageDetector)
    .use(initReactI18next)
    .init({
        resources: {
            en: { translation: { ...en, ...narrativesEn } },
            es: { translation: { ...es, ...narrativesEs } }
        },
        fallbackLng: 'es', // Default to Spanish as requested
        interpolation: {
            escapeValue: false // React already safes from xss
        },
        detection: {
            order: ['localStorage', 'navigator'],
            caches: ['localStorage']
        }
    });

export default i18n;
