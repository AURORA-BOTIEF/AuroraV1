// src/utils/s3ImageLoader.js
import { fetchAuthSession } from 'aws-amplify/auth';
import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3';

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

        // Create S3 client with user's IAM credentials
        const { S3Client, PutObjectCommand } = await import('@aws-sdk/client-s3');

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

        // Upload to S3
        const command = new PutObjectCommand({
            Bucket: BUCKET_NAME,
            Key: s3Key,
            Body: new Uint8Array(arrayBuffer),
            ContentType: file.type || 'image/png'
        });

        await s3Client.send(command);

        // Return the S3 URL
        const s3Url = `https://${BUCKET_NAME}.s3.amazonaws.com/${s3Key}`;
        console.log(`✓ Uploaded image: ${s3Key}`);

        return s3Url;
    } catch (error) {
        console.error('Failed to upload image:', error);
        throw error;
    }
}
