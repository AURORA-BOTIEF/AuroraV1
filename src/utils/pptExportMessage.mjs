/** Messages for the PPT export quality gate (HTTP 422). Spanish by default. */

import { uiLanguage } from './courseStatus.mjs';

export function pptExportMessage(status, body, lang) {
    const copy = uiLanguage(lang) === 'en'
        ? {
            rejected: 'The presentation was not exported. The deck failed the quality check.',
            generic: 'Could not download the PPT.',
        }
        : {
            rejected: 'La presentación no se exportó. El deck no pasó el control de calidad.',
            generic: 'No se pudo descargar el PPT.',
        };
    const payload = body || {};
    if (status === 422) {
        const issues = (payload.quality_report && payload.quality_report.issues) || [];
        const detail = issues
            .slice(0, 3)
            .map((issue) => issue.message || issue.code)
            .filter(Boolean)
            .join(' ');
        return detail ? `${copy.rejected} ${detail}` : copy.rejected;
    }
    return payload.error || copy.generic;
}
