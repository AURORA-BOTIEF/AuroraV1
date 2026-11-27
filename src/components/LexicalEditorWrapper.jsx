import React, { useEffect, useRef, useState, useCallback } from 'react';
import { LexicalComposer } from '@lexical/react/LexicalComposer';
import { RichTextPlugin } from '@lexical/react/LexicalRichTextPlugin';
import { ContentEditable } from '@lexical/react/LexicalContentEditable';
import { HistoryPlugin } from '@lexical/react/LexicalHistoryPlugin';
import { $getRoot, $getSelection, $isRangeSelection } from 'lexical';
import { $generateHtmlFromNodes, $generateNodesFromDOM } from '@lexical/html';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { uploadImageToS3, replaceDataUrlsWithS3Urls } from '../utils/s3ImageLoader';
import './LexicalEditorWrapper.css';

// Minimal editor config
const editorConfig = {
    namespace: 'LexicalEditor',
    onError(error) {
        console.error('Lexical error:', error);
    }
};

export default function LexicalEditorWrapper({ initialHtml = '', readOnly = false, onChange, projectFolder }) {
    const [html, setHtml] = useState(initialHtml);
    const [displayHtml, setDisplayHtml] = useState(initialHtml);
    const composerConfig = { ...editorConfig };

    // We'll use the editor instance to insert image nodes. Use a child to get the editor.
    const EditorInitializer = ({ }) => {
        const [editor] = useLexicalComposerContext();

        // Register an update listener so we can serialize HTML using the editor instance
        useEffect(() => {
            const unregister = editor.registerUpdateListener(({ editorState }) => {
                try {
                    editorState.read(() => {
                        try {
                            const out = $generateHtmlFromNodes(editor);
                            setHtml(out);
                            onChange && onChange(out);
                        } catch (e) {
                            // serialization may fail for some node types; keep going
                            console.error('Lexical onChange conversion failed:', e);
                        }
                    });
                } catch (e) {
                    console.error('Error in update listener:', e);
                }
            });
            return () => unregister();
        }, [editor, onChange]);

        // Set initial HTML if provided. Wrap the content in a container so plain text
        // becomes an element and @lexical/html generates element nodes that can be
        // appended to the root (root only accepts element/decorator nodes).
        // Re-inject initialHtml whenever it changes so switching into edit mode
        // or loading a new lesson/version applies the latest HTML (including <img>
        // tags) into the editor. Previously this only ran on mount which meant
        // edits after initial render showed the raw markdown or empty content.
        useEffect(() => {
            try {
                const wrapped = `<div>${initialHtml || ''}</div>`;
                const parser = new DOMParser();
                const dom = parser.parseFromString(wrapped, 'text/html');
                editor.update(() => {
                    const nodes = $generateNodesFromDOM(editor, dom.body);
                    const root = $getRoot();
                    root.clear();
                    for (const node of nodes) {
                        root.append(node);
                    }
                });
                // keep a copy for the read-only renderer
                setDisplayHtml(initialHtml || '');
            } catch (e) {
                console.warn('Failed to set initial HTML in Lexical editor:', e);
            }
        }, [initialHtml, editor]);

        // Paste handler scoped to document but uses editor.update to insert nodes
        useEffect(() => {
            const handler = async (e) => {
                try {
                    const clipboard = e.clipboardData || window.clipboardData;
                    if (!clipboard) return;

                    const files = Array.from(clipboard.files || []).filter(f => f.type && f.type.startsWith('image/'));
                    if (files.length > 0) {
                        e.preventDefault();
                        for (const file of files) {
                            try {
                                const s3Url = await uploadImageToS3(file, projectFolder);
                                editor.update(() => {
                                    const parser = new DOMParser();
                                    const dom = parser.parseFromString(`<div><img src="${s3Url}" alt="pasted-image" /></div>`, 'text/html');
                                    const nodes = $generateNodesFromDOM(editor, dom.body);
                                    const selection = $getSelection();
                                    if ($isRangeSelection(selection)) {
                                        selection.insertNodes(nodes);
                                    } else {
                                        const root = $getRoot();
                                        for (const n of nodes) root.append(n);
                                    }
                                });
                            } catch (err) {
                                console.error('Failed to upload pasted image (Lexical wrapper):', err);
                            }
                        }
                        return;
                    }

                    const htmlData = clipboard.getData('text/html');
                    if (htmlData && htmlData.includes('data:')) {
                        e.preventDefault();
                        try {
                            const updated = await replaceDataUrlsWithS3Urls(htmlData, projectFolder);
                            // Convert updated HTML into nodes and insert at selection; wrap in container
                            const wrapped = `<div>${updated}</div>`;
                            const parser = new DOMParser();
                            const dom = parser.parseFromString(wrapped, 'text/html');
                            editor.update(() => {
                                const nodes = $generateNodesFromDOM(editor, dom.body);
                                const selection = $getSelection();
                                if ($isRangeSelection(selection)) {
                                    selection.insertNodes(nodes);
                                } else {
                                    const root = $getRoot();
                                    for (const n of nodes) root.append(n);
                                }
                            });
                        } catch (err) {
                            console.error('Failed to replace data URLs on paste (Lexical wrapper):', err);
                        }
                    }
                } catch (err) {
                    console.error('Lexical wrapper paste handler error:', err);
                }
            };

            document.addEventListener('paste', handler);
            return () => document.removeEventListener('paste', handler);
        }, [editor, projectFolder]);

        return null;
    };

    return (
        // If caller requested read-only rendering, show rendered HTML directly so
        // images and the markdown->HTML conversion are preserved exactly as the
        // book author expected. This avoids requiring extra Lexical node plugins
        // for images and ensures the read-only view is identical to the prior
        // editor's rendered output.
        readOnly ? (
            <div className="lexical-readonly" dangerouslySetInnerHTML={{ __html: displayHtml }} />
        ) : (
            <LexicalComposer initialConfig={composerConfig}>
                <div className="lexical-wrapper">
                    <RichTextPlugin
                        contentEditable={<ContentEditable className="lexical-content-editable" />}
                        placeholder={<div className="lexical-placeholder">Escribe aquí...</div>}
                    />
                    {/* We use a registered update listener (in EditorInitializer) to serialize changes */}
                    <HistoryPlugin />
                    <EditorInitializer />
                </div>
            </LexicalComposer>
        )
    );
}
