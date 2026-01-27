
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
