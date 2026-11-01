
import { jsPDF } from "jspdf";
import fs from "fs";

console.log("Generating PDF...");

try {
    const pdf = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: 'a4'
    });

    const margin = 20;
    let yPosition = 20;

    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(10);

    // Cleaning function to test
    const cleanPdfText = (text) => {
        if (!text) return '';
        // 1. Remove control characters (0-31) except newline (10)
        let cleaned = text.replace(/[\x00-\x09\x0B-\x1F]/g, '');

        // 2. Generic Frequency Sanitizer
        const charCounts = {};
        const len = cleaned.length;
        if (len > 10) {
            for (let i = 0; i < len; i++) {
                const char = cleaned[i];
                if (/[a-zA-Z0-9\s.,;:'"()áéíóúÁÉÍÓÚñÑ-]/.test(char)) continue;
                charCounts[char] = (charCounts[char] || 0) + 1;
            }

            for (const [char, count] of Object.entries(charCounts)) {
                if (count > 4 && count > len * 0.1) {
                    const charCode = char.charCodeAt(0);
                    console.log(`🔥 CLEANER: Detected noise char '${char}' (Code: ${charCode}). Occurrences: ${count}. STRIPPING.`);
                    const safeChar = char.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                    const regex = new RegExp(safeChar, 'g');
                    cleaned = cleaned.replace(regex, '');
                }
            }
        }

        // 3. Last resort fallback
        cleaned = cleaned.replace(/&(?=\S)/g, '');
        return cleaned;
    };

    // Test 4: Corrupted text with '&' artifacts
    console.log("Test: Corrupted text cleaning");
    // This string simulates the screenshot corruption: & char & char & ...
    const corruptedText = "&S&e&l&e&c&c&i&o&n&a& &\"&C&r&e&a&r&\"& !& &\"&N&u&e&v&o& &c&o&p&i&l&o&t&\"";

    const cleanedText = cleanPdfText(corruptedText);
    console.log(`Original: "${corruptedText}"`);
    console.log(`Cleaned:  "${cleanedText}"`);

    // Test 5: Generic corruption (e.g. pipes)
    console.log("Test: Generic Pipe corruption");
    const pipeText = "|S|e|l|e|c|c|i|o|n|a| |P|r|u|e|b|a|";
    const cleanedPipe = cleanPdfText(pipeText);
    console.log(`Original Pipe: "${pipeText}"`);
    console.log(`Cleaned Pipe:  "${cleanedPipe}"`);

    pdf.text("Cleaned Text Check:", margin, yPosition);
    yPosition += 7;
    pdf.text(cleanedText, margin, yPosition);

    // Test 2: Split text with null bytes
    console.log("Test: string with null bytes");
    const textWithNulls = "3. S\u0000e\u0000l\u0000e\u0000c\u0000c\u0000i\u0000o\u0000n\u0000a";
    try {
        const wrappedLinesNulls = pdf.splitTextToSize(textWithNulls, 170);
        console.log("Wrapped lines (nulls):", wrappedLinesNulls);
        for (const line of wrappedLinesNulls) {
            pdf.text(line, margin, yPosition);
            yPosition += 7;
        }
    } catch (e) {
        console.log("Error with nulls:", e.message);
    }

    // Test 3: Split text with BOM
    console.log("Test: string with BOM");
    const textWithBOM = "3. \uFEFFSelecciona";
    const wrappedLinesBOM = pdf.splitTextToSize(textWithBOM, 170);
    for (const line of wrappedLinesBOM) {
        pdf.text(line, margin, yPosition);
        yPosition += 7;
    }

    const output = pdf.output('arraybuffer');
    fs.writeFileSync('test_output.pdf', Buffer.from(output));
    console.log("PDF generated: test_output.pdf");

} catch (e) {
    console.error("Error:", e);
}
