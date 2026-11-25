/** Client-visible course status. Spanish is the default; English follows an explicit lang or the browser. */

export function uiLanguage(explicit) {
    // The product UI is Spanish. English is opt-in through the lang argument.
    if (explicit && String(explicit).toLowerCase().startsWith('en')) return 'en';
    return 'es';
}

const COPY = {
    es: {
        needsReviewLabel: 'NECESITA REVISIÓN',
        needsReviewHeadline: 'El curso no se entregó: hay laboratorios con hallazgos de alta confianza que necesitan revisión.',
        warningsLabel: 'COMPLETADO CON ADVERTENCIAS',
        warningsHeadline: 'El contenido principal se generó, pero falló un componente que no bloquea el curso (guía de configuración, auditoría o decks).',
        linksLabel: 'ENLACES ROTOS',
        linksHeadline: 'El curso no se entregó: hay enlaces públicos muertos (404, 410 o un dominio inexistente).',
        failedHeadline: 'La generación falló.',
    },
    en: {
        needsReviewLabel: 'NEEDS REVIEW',
        needsReviewHeadline: 'The course was not delivered: labs still have high-confidence findings that need review.',
        warningsLabel: 'COMPLETED WITH WARNINGS',
        warningsHeadline: 'The main content was generated, but a non-blocking component failed (setup guide, audit, or decks).',
        linksLabel: 'BROKEN LINKS',
        linksHeadline: 'The course was not delivered: public links are dead (404, 410, or an unknown domain).',
        failedHeadline: 'Generation failed.',
    },
};

function text(value) {
    return typeof value === 'string' ? value : '';
}

export function presentCourseStatus(payload, lang) {
    const body = payload || {};
    const copy = COPY[uiLanguage(lang)];
    const quality = body.quality_status || body.course_status;
    const needsReview = body.needs_review === true || quality === 'needs_review' || body.course_status === 'needs_review';
    const warnings = Array.isArray(body.generation_warnings) ? body.generation_warnings : [];
    const linkAudit = body.course_status === 'link_audit_failed'
        || body.error === 'LinkAuditFailed'
        || (typeof body.error === 'string' && body.error.includes('Enlaces públicos muertos'));

    if (needsReview) {
        const detail = body.error || body.quality_summary || '';
        return {
            label: copy.needsReviewLabel,
            code: 'needs_review',
            tone: 'needs_review',
            headline: copy.needsReviewHeadline,
            detail: text(detail),
        };
    }

    if (linkAudit) {
        return {
            label: copy.linksLabel,
            code: 'link_audit_failed',
            tone: 'failed',
            headline: copy.linksHeadline,
            detail: text(body.error),
        };
    }

    if (body.course_status === 'SUCCEEDED_WITH_WARNINGS' || (body.status === 'SUCCEEDED' && warnings.length > 0)) {
        const components = warnings.map((item) => item.component || item.code).filter(Boolean);
        const detail = components.length ? components.join(', ') : '';
        return {
            label: copy.warningsLabel,
            code: 'succeeded_with_warnings',
            tone: 'warning',
            headline: copy.warningsHeadline,
            detail,
        };
    }

    if (body.status === 'SUCCEEDED' || quality === 'passed' || body.course_status === 'passed') {
        return {
            label: 'SUCCEEDED',
            code: 'passed',
            tone: 'passed',
            headline: '',
            detail: '',
        };
    }

    if (body.status === 'FAILED' || quality === 'failed' || body.course_status === 'failed') {
        return {
            label: 'FAILED',
            code: 'failed',
            tone: 'failed',
            headline: copy.failedHeadline,
            detail: text(body.error),
        };
    }

    if (body.status === 'RUNNING') {
        return { label: 'RUNNING', code: 'running', tone: 'running', headline: '', detail: '' };
    }

    return {
        label: body.status || 'UNKNOWN',
        code: 'pending',
        tone: 'pending',
        headline: '',
        detail: '',
    };
}
