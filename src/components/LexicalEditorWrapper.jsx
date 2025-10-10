import React, { useEffect, useRef, useState, useCallback } from 'react';
import { LexicalComposer } from '@lexical/react/LexicalComposer';
import { RichTextPlugin } from '@lexical/react/LexicalRichTextPlugin';
import { ContentEditable } from '@lexical/react/LexicalContentEditable';
import { OnChangePlugin } from '@lexical/react/LexicalOnChangePlugin';
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
    const composerConfig = { ...editorConfig };

    const handleChange = useCallback((editorState) => {
        try {
            let out = '';
            editorState.read(() => {
                // Generate HTML from nodes for a richer serialization
                out = $generateHtmlFromNodes(editorState);
            });
            setHtml(out);
            onChange && onChange(out);
        } catch (e) {
            console.error('Lexical onChange conversion failed:', e);
        }
    }, [onChange]);

    // We'll use the editor instance to insert image nodes. Use a child to get the editor.
    const EditorInitializer = ({ }) => {
        const [editor] = useLexicalComposerContext();

        // Set initial HTML if provided
        useEffect(() => {
            if (!initialHtml) return;
            try {
                const parser = new DOMParser();
                const dom = parser.parseFromString(initialHtml, 'text/html');
                editor.update(() => {
                    const nodes = $generateNodesFromDOM(editor, dom);
                    const root = $getRoot();
                    root.clear();
                    for (const node of nodes) {
                        root.append(node);
                    }
                });
            } catch (e) {
                console.warn('Failed to set initial HTML in Lexical editor:', e);
            }
            // eslint-disable-next-line react-hooks/exhaustive-deps
        }, []);

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
                                    const dom = parser.parseFromString(`<img src="${s3Url}" alt="pasted-image" />`, 'text/html');
                                    const nodes = $generateNodesFromDOM(editor, dom);
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
                            // Convert updated HTML into nodes and insert at selection
                            const parser = new DOMParser();
                            const dom = parser.parseFromString(updated, 'text/html');
                            editor.update(() => {
                                const nodes = $generateNodesFromDOM(editor, dom);
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
        <LexicalComposer initialConfig={composerConfig}>
            <div className="lexical-wrapper">
                <RichTextPlugin
                    contentEditable={<ContentEditable className="lexical-content-editable" />}
                    placeholder={<div className="lexical-placeholder">Escribe aquí...</div>}
                />
                <OnChangePlugin onChange={handleChange} />
                <HistoryPlugin />
                <EditorInitializer />
            </div>
        </LexicalComposer>
    );
}
