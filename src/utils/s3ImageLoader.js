// src/utils/s3ImageLoader.js
import { fetchAuthSession } from 'aws-amplify/auth';
import { S3Client, GetObjectCommand, PutObjectCommand } from '@aws-sdk/client-s3';

const BUCKET_NAME = 'crewai-course-artifacts';
const REGION = 'us-east-1';

/**
 * Replace S3 URLs in content with data URLs using IAM credentials
 * This allows images to be displayed even though the bucket is private
 */
export async function replaceS3UrlsWithDataUrls(content) {
    if (!content) return content;

    // Find all S3 image URLs in the content
    // Matches both: ![alt](https://bucket.s3.amazonaws.com/path) and ![[alt]](url)
    const s3UrlPattern = /!\[+([^\]]*)\]+\((https:\/\/[^\/]+\.s3\.amazonaws\.com\/[^)]+)\)/g;

    const matches = [];
    let match;
    while ((match = s3UrlPattern.exec(content)) !== null) {
        matches.push({
            fullMatch: match[0],
            alt: match[1],
            url: match[2]
        });
    }

    if (matches.length === 0) {
        return content;
    }

    // Get AWS credentials from Cognito
    const session = await fetchAuthSession();
    if (!session.credentials) {
        console.error('No AWS credentials available');
        return content;
    }

    // Create S3 client with user's IAM credentials
    const s3Client = new S3Client({
        region: REGION,
        credentials: session.credentials
    });

    // Replace each S3 URL with a data URL
    let updatedContent = content;

    for (const item of matches) {
        try {
            // Extract S3 key from URL
            // Format: https://bucket.s3.amazonaws.com/path/to/file.png
            const urlParts = item.url.split('.s3.amazonaws.com/');
            if (urlParts.length !== 2) continue;

            const s3Key = urlParts[1];

            // Get the image from S3
            const command = new GetObjectCommand({
                Bucket: BUCKET_NAME,
                Key: s3Key
            });

            const response = await s3Client.send(command);

            // Convert response body to blob
            const blob = await response.Body.transformToByteArray();

            // Convert blob to base64 data URL
            const base64 = btoa(
                new Uint8Array(blob).reduce((data, byte) => data + String.fromCharCode(byte), '')
            );

            // Determine content type from the file extension or response
            const contentType = response.ContentType || 'image/png';
            const dataUrl = `data:${contentType};base64,${base64}`;

            // Replace the S3 URL with the data URL
            const replacement = `![${item.alt}](${dataUrl})`;
            updatedContent = updatedContent.replace(item.fullMatch, replacement);

            console.log(`✓ Loaded image: ${s3Key}`);
        } catch (error) {
            console.error(`Failed to load image ${item.url}:`, error);
            // Keep the original URL if loading fails
        }
    }

    return updatedContent;
}

/**
 * Upload an image to S3 and return the S3 URL
 * @param {File} file - The image file to upload
 * @param {string} projectFolder - The project folder (e.g., "251008-custom-course-05")
 * @returns {Promise<string>} - The S3 URL of the uploaded image
 */
export async function uploadImageToS3(file, projectFolder) {
    try {
        // Get AWS credentials from Cognito
        const session = await fetchAuthSession();
        if (!session.credentials) {
            throw new Error('No AWS credentials available');
        }

        // Create S3 client with user's IAM credentials (Cognito identity)
        const s3Client = new S3Client({
            region: REGION,
            credentials: session.credentials
        });

        // Generate unique filename
        const timestamp = Date.now();
        const randomId = Math.random().toString(36).substring(7);
        const extension = file.name.split('.').pop();
        const fileName = `user-upload-${timestamp}-${randomId}.${extension}`;
        const s3Key = `${projectFolder}/images/${fileName}`;

        // Read file as array buffer
        const arrayBuffer = await file.arrayBuffer();

        // Upload to S3 using the authenticated credentials. Objects are written
        // with the provided key and will be accessible later by the app using
        // authenticated SDK calls (we do NOT return a presigned URL here since
        // authentication is handled by Cognito/IAM credentials).
        const command = new PutObjectCommand({
            Bucket: BUCKET_NAME,
            Key: s3Key,
            Body: new Uint8Array(arrayBuffer),
            ContentType: file.type || 'image/png'
        });

        await s3Client.send(command);
        // Return the canonical S3 object URL (not presigned). The frontend
        // may need authenticated SDK calls to fetch the object if the bucket
        // is private; but using Cognito/IAM we rely on the app to fetch when
        // necessary. For immediate preview we recommend inserting a local
        // blob URL and swapping to this URL after the upload completes.
        console.log(`✓ Uploaded image: ${s3Key}`);
        return `https://${BUCKET_NAME}.s3.amazonaws.com/${s3Key}`;
    } catch (error) {
        console.error('Failed to upload image:', error);
        throw error;
    }
}

/**
 * Replace inlined data: image URLs in HTML/markdown with S3 URLs by uploading
 * the images to the project's images/ prefix. Returns updated content.
 * Supports <img src="data:..."> in HTML and markdown image syntaxes.
 */
export async function replaceDataUrlsWithS3Urls(content, projectFolder) {
    if (!content) return content;

    // Find data URL images in both HTML img tags and markdown image syntax
    const dataUrlPatternImg = /<img[^>]*src=\"(data:[^\"]+)\"[^>]*>/gim;
    const dataUrlPatternMd = /!\[([^\]]*)\]\((data:[^)]+)\)/gim;

    const session = await fetchAuthSession();
    if (!session || !session.credentials) {
        console.error('No AWS credentials available for image upload');
        return content;
    }

    // We'll reuse uploadImageToS3 by creating File objects from data URLs
    let updated = content;

    // Helper to convert dataURL to File-like object and upload
    async function uploadDataUrl(dataUrl, suggestedName) {
        // Fetch the data URL as a blob
        const res = await fetch(dataUrl);
        const blob = await res.blob();
        const type = blob.type || 'image/png';
        const extension = type.split('/').pop() || 'png';
        const fileName = suggestedName || `pasted-${Date.now()}.${extension}`;
        // Create a File (browser) - Upload helper accepts File
        const file = new File([blob], fileName, { type });
        const s3Url = await uploadImageToS3(file, projectFolder);
        return s3Url;
    }

    // Replace HTML <img src="data:...">
    let match;
    const imgPromises = [];
    while ((match = dataUrlPatternImg.exec(content)) !== null) {
        const full = match[0];
        const dataUrl = match[1];
        const promise = (async () => {
            try {
                const s3Url = await uploadDataUrl(dataUrl);
                // build replacement img tag preserving alt/style attributes is complex;
                // simplest: replace src attribute only
                const replaced = full.replace(dataUrl, s3Url);
                updated = updated.replace(full, replaced);
            } catch (e) {
                console.error('Failed to upload pasted image from HTML', e);
            }
        })();
        imgPromises.push(promise);
    }

    // Replace markdown images ![alt](data:...)
    while ((match = dataUrlPatternMd.exec(content)) !== null) {
        const full = match[0];
        const alt = match[1];
        const dataUrl = match[2];
        const promise = (async () => {
            try {
                const s3Url = await uploadDataUrl(dataUrl);
                const replacement = `![${alt}](${s3Url})`;
                updated = updated.replace(full, replacement);
            } catch (e) {
                console.error('Failed to upload pasted image from markdown', e);
            }
        })();
        imgPromises.push(promise);
    }

    await Promise.all(imgPromises);
    return updated;
}

/**
 * Fetch a private S3 object using Cognito-authenticated credentials and return
 * a local blob URL suitable for immediate <img src="..."> display in the browser.
 * Accepts either a full S3 URL (https://bucket.s3.amazonaws.com/key) or an S3 key.
 */
export async function getBlobUrlForS3Object(s3PathOrUrl) {
    try {
        // Determine key
        // Determine key
        let s3Key = s3PathOrUrl;
        if (s3PathOrUrl.startsWith('http')) {
            try {
                const url = new URL(s3PathOrUrl);
                // pathname includes the leading slash, e.g. "/folder/image.png"
                // We want "folder/image.png"
                s3Key = url.pathname.substring(1);

                // URL decode the key (e.g. %20 -> space)
                s3Key = decodeURIComponent(s3Key);

                console.log(`[s3ImageLoader] Extracted key: ${s3Key} from URL: ${s3PathOrUrl}`);
            } catch (e) {
                console.error('[s3ImageLoader] Failed to parse URL:', s3PathOrUrl, e);
                // Fallback to original logic if URL parsing fails
                const parts = s3PathOrUrl.split('.s3.amazonaws.com/');
                if (parts.length === 2) s3Key = parts[1];
            }
        }

        const session = await fetchAuthSession();
        if (!session || !session.credentials) throw new Error('No AWS credentials available');

        const s3Client = new S3Client({ region: REGION, credentials: session.credentials });
        const cmd = new GetObjectCommand({ Bucket: BUCKET_NAME, Key: s3Key });
        const resp = await s3Client.send(cmd);

        // resp.Body may be a stream/array; convert to byte array then blob
        let byteArray;
        if (resp.Body && typeof resp.Body.transformToByteArray === 'function') {
            byteArray = await resp.Body.transformToByteArray();
        } else if (resp.Body && typeof resp.Body.arrayBuffer === 'function') {
            const ab = await resp.Body.arrayBuffer();
            byteArray = new Uint8Array(ab);
        } else {
            // Try Response approach
            const buffer = await new Response(resp.Body).arrayBuffer();
            byteArray = new Uint8Array(buffer);
        }

        const blob = new Blob([byteArray], { type: resp.ContentType || 'application/octet-stream' });
        const blobUrl = URL.createObjectURL(blob);
        return blobUrl;
    } catch (e) {
        console.error('Failed to fetch S3 object as blob URL', e);
        throw e;
    }
}
