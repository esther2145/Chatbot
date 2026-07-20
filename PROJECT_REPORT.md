# NSSF Chatbot Project Report

## Project Overview

This project involved developing an NSSF Uganda chatbot named Nicky. The chatbot was designed to answer user questions about NSSF services, membership, contributions, benefits, employer services, and self-service options. The system started as a Python chatbot and was later improved with voice support, different user interfaces, chat history, and a more structured backend and frontend setup.

## Activities Done

1. Built the chatbot backend

   The chatbot backend was created to process user questions and return answers using an AI model. The assistant was connected to an API so that user questions could be sent to an external language model and responses could be returned to the application.

2. Added NSSF website data

   A scraper was used to collect information from NSSF Uganda web pages. The scraped content was cached locally so the chatbot could use NSSF-related information when answering questions.

3. Added voice input and voice output

   Voice recognition was added so users could ask questions by speaking. Text-to-speech was also added so the chatbot could read answers aloud. A voice toggle was later introduced so users could choose between spoken replies and text-only replies.

4. Developed user interfaces

   A Tkinter desktop UI was created first. Later, a browser-based UI was added to provide a more modern interface. The web interface included chat input, response display, microphone input, voice reply controls, and styling improvements.

5. Added chat history

   A database module was introduced to store chat sessions and messages. This allowed users to view previous conversations, create new chats, and delete old sessions.

6. Improved project structure

   The project was reorganized into a clearer structure with backend, frontend, ingestion, environment configuration, and Docker support. This made the project easier to run, maintain, and extend.

## Challenges Faced

1. API limits and errors

   The chatbot depended on an external AI API. Sometimes the API returned usage limit or rate limit errors, which meant the chatbot could not answer until the limit reset or another API key/model was used.

2. UI responsiveness issues

   Some buttons stopped responding after adding new features. This was caused by JavaScript errors and mismatched variable names in the web UI. A small script error could stop the whole page from working.

3. Voice support differences

   Voice output worked differently in the Python desktop UI and the browser UI. The desktop version used Python text-to-speech, while the browser version used the browser speech system.

4. Managing chat history

   Adding chat history required keeping track of sessions, saving messages correctly, and making sure the selected conversation matched the backend session.

5. Encoding problems

   Some files had special characters that displayed incorrectly or caused terminal errors. This showed the importance of using clean UTF-8 text and avoiding unsupported symbols in console output.

6. Port and server issues

   When running the web UI, old server processes or occupied ports could cause the page to load an older version or fail to start. Port fallback and clearer startup messages helped reduce this problem.

## Skills Learnt

1. Working with APIs

   I learnt how an application communicates with an external AI service through an API key and API requests.

2. Python backend development

   I gained experience building Python modules for chatbot logic, web scraping, voice handling, database storage, and server-side routes.

3. Frontend development

   I learnt how HTML, CSS, and JavaScript work together to create an interactive web interface with buttons, chat messages, microphone controls, and dynamic updates.

4. Voice recognition and text-to-speech

   I learnt how to add voice input and spoken replies, and how voice features differ between desktop applications and web browsers.

5. Database usage

   I learnt how to store chat sessions and messages using SQLite, and how to retrieve previous conversations for chat history.

6. Debugging

   I improved my debugging skills by checking syntax errors, testing API endpoints, reading error messages, and identifying issues in both Python and JavaScript.

7. Project organization

   I learnt how to separate a project into backend, frontend, ingestion, and configuration parts, making it easier to maintain and deploy.

## Conclusion

The project successfully developed an NSSF Uganda chatbot with text chat, voice interaction, web-based UI, chat history, and backend support. The work improved understanding of APIs, AI chatbots, frontend design, backend development, voice features, and debugging. Although challenges such as API limits, UI errors, and server issues were encountered, solving them helped strengthen practical software development skills.
