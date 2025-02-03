const fs = require('fs');
const path = require('path');

// Define the path to the text file
const filePath = path.join(__dirname, 'input.txt');

function generateUniqueId() {
  return Math.random().toString(16).substr(2, 8);
}

// Read the file content
fs.readFile(filePath, 'utf8', (err, data) => {
  if (err) {
    console.error('Error reading file:', err);
    return;
  }

  // Split the content into sections
  const sections = data.split('________________');

  // Parse each section
  const parsedSections = sections.map((section, index) => {
    const lines = section.trim().split('\n');

    if (lines.length === 0) {
      return null;
    }

    const title = lines[0];
    const tests = [];
    let currentQuestion = null;
    let currentAnswer = null;

    for (let i = 1; i < lines.length; i++) {
      const line = lines[i];
      const emptyLine = line.trim().length === 0;

      if (emptyLine && currentQuestion && currentAnswer) {
        // We're done here
        tests.push({
          id: generateUniqueId(),
          question: currentQuestion,
          correct_chunks: [],
          corrent_answer: currentAnswer.join('\n')
        });
        currentQuestion = null;
        currentAnswer = null;
      } else if (line.startsWith('Answer:')) {
        currentAnswer = [line.replace('Answer:', '').trim()];
      } else if (emptyLine) {
        console.log("The line is empty.");
      } else if (!currentAnswer && !currentQuestion) {
        currentQuestion = line.trim();
      } else if (currentAnswer) {
        console.log(line);
        currentAnswer.push(line.trim());
      }

    }
    console.log(tests)
    // End Loop


    return {
      id: generateUniqueId(),
      title,
      tests
    };
  }).filter(section => section !== null);

  // Convert the parsed sections to JSON
  const jsonOutput = JSON.stringify(parsedSections, null, 2);

  // Write the JSON output to a file
  const outputFilePath = path.join(__dirname, 'parsedOutput.json');
  fs.writeFile(outputFilePath, jsonOutput, 'utf8', err => {
    if (err) {
      console.error('Error writing JSON file:', err);
      return;
    }
    console.log('JSON file has been saved:', outputFilePath);
  });
});