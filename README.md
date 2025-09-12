# CV & Cover Letter Generator

A complete Streamlit + LangChain application that generates ATS-optimized CV packages and cover letters by analyzing job descriptions, candidate experience, and mimicking CV formatting styles.

## 🎯 Features

- **PDF Processing**: Upload and parse four PDFs (Job Description, Experience Superset, Skills Superset, Sample CV)
- **RAG-Powered Generation**: Uses FAISS vector store and HuggingFace embeddings for context-aware content generation
- **CV Package Generation**: Creates career summary (≤40 words), exactly 8 SAR bullets with two-word headings, and 10 skills (≤2 words each)
- **Cover Letter Generation**: Generates ATS-optimized cover letters (3-4 paragraphs, ≤250 words)
- **Style Matching**: Automatically extracts and applies formatting style from Sample CV
- **Multi-Format Export**: Download as .txt, .md, and .docx files
- **Validation & Retry**: Automatic validation with retry logic for format compliance
- **Professional UI**: Clean Streamlit interface with real-time feedback

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- OpenAI API key

### Installation

1. **Clone and setup**:
   ```bash
   cd cv-coverletter-streamlit
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   echo "OPENAI_API_KEY=your_api_key_here" > .env
   ```

3. **Run application**:
   ```bash
   streamlit run app.py
   ```

4. **Open browser**: Navigate to `http://localhost:8501`

## 📁 Project Structure

```
cv-coverletter-streamlit/
├── app.py                          # Main Streamlit application
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment template
├── README.md                       # This file
├── prompts/
│   ├── prompt4_combined.txt        # CV package generation prompt
│   └── prompt5_coverletter.txt     # Cover letter generation prompt
├── services/
│   ├── ingest.py                   # PDF processing & FAISS vector store
│   ├── rag.py                      # RAG retrieval and context building
│   ├── style_extract.py            # Sample CV style analysis
│   └── llm.py                      # OpenAI LLM service with validation
├── templates/
│   ├── cv_default.jinja.md         # Default CV template
│   ├── cv_two_col.jinja.md         # Two-column CV template
│   └── sections_map.json           # Section mapping configuration
├── exporters/
│   ├── markdown_export.py          # Markdown format export
│   └── docx_export.py              # Word document export
├── utils/
│   ├── text.py                     # Text processing utilities
│   └── style.py                    # Style matching and application
├── outputs/                        # Generated files (auto-created)
├── .streamlit/
│   └── config.toml                 # Streamlit configuration
└── tests/
    └── test_rag.py                 # Test files (optional)
```

## 🔧 Usage

### Step 1: Upload Documents
Upload four required PDFs:
1. **Job Description PDF**: Target job posting you're applying for
2. **Experience Superset PDF**: Comprehensive document containing all your work experience and achievements
3. **Skills Superset PDF**: Document containing all your technical and soft skills
4. **Sample CV PDF**: CV whose formatting style you want to mimic

### Step 2: Generate Content
Choose generation mode:
- **CV Package**: Career summary + 8 SAR bullets + 10 skills
- **Cover Letter**: 3-4 paragraphs, ≤250 words
- **Both**: Generate complete application package

### Step 3: Validate & Review
- Real-time validation of word counts and formatting
- Automatic retry on validation failures
- Manual editing and regeneration options

### Step 4: Export & Download
- Multiple formats: .txt, .md, .docx
- Styled formatting matching Sample CV
- Batch download capabilities

## ⚙️ Configuration

### Model Selection
Choose between:
- **gpt-4o-mini**: Fast and cost-effective
- **gpt-4o**: Higher quality output

### Generation Settings
- Auto-retry on validation failure
- Maximum retry attempts (1-5)
- Context preview options

### Export Options
- Text format (.txt)
- Markdown format (.md)  
- Word document (.docx)

## 🧠 Technical Details

### RAG Architecture
- **Embeddings**: HuggingFace `all-MiniLM-L6-v2`
- **Vector Store**: FAISS in-memory
- **Chunking**: RecursiveCharacterTextSplitter (1000 chars, 200 overlap)
- **Retrieval**: Similarity search with score thresholding

### LLM Integration
- **Models**: OpenAI GPT-4o-mini/GPT-4o
- **Temperature**: 0.2 for consistency
- **Retry Logic**: Automatic validation and improvement
- **Context Management**: 8000 character limit

### Style Processing
- Automatic bullet style detection (•, -, *, →, etc.)
- Heading format analysis (ALL_CAPS, Title_Case)
- Contact format recognition (horizontal, vertical, block)
- Date format extraction and matching

## 📋 Validation Requirements

### CV Package
- **Career Summary**: Exactly ≤40 words
- **SAR Bullets**: Exactly 8 bullets with two-word headings
- **Skills**: Exactly 10 skills, ≤2 words each

### Cover Letter
- **Word Count**: ≤250 words
- **Structure**: 3-4 paragraphs
- **Content**: ATS-optimized with job-specific keywords

## 🛠️ Development

### Adding New Features

1. **New Export Format**:
   ```python
   # Add to exporters/ directory
   # Update app.py export handling
   # Add to UI format selection
   ```

2. **Custom Templates**:
   ```python
   # Add Jinja2 template to templates/
   # Update section mappings in sections_map.json
   # Register in markdown_export.py
   ```

3. **New Validation Rules**:
   ```python
   # Update services/llm.py CVPackageValidator
   # Add to utils/text.py ContentValidator
   # Update UI validation display
   ```

### Testing
```bash
# Install test dependencies
pip install pytest pytest-cov

# Run tests
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=services --cov=utils
```

### Logging
Application uses Python logging:
- INFO level for normal operations
- ERROR level for exceptions
- Logs to console (Streamlit terminal)

## 📊 Performance

### Typical Processing Times
- PDF ingestion: 2-5 seconds per document
- Vector embedding: 3-7 seconds for all chunks
- CV generation: 10-20 seconds (GPT-4o-mini)
- Cover letter generation: 5-10 seconds
- Style extraction: 1-2 seconds

### Resource Usage
- Memory: ~500MB-1GB (depends on document size)
- CPU: Light usage during processing
- Storage: Minimal (outputs/ directory only)

## 🔒 Security & Privacy

- API keys stored in environment variables
- No data persistence beyond session
- Temporary file handling for uploads
- No external data sharing

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push branch: `git push origin feature/amazing-feature`
5. Submit pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Troubleshooting

### Common Issues

1. **"OpenAI API key not found"**
   - Check .env file exists and contains valid API key
   - Restart Streamlit after adding key

2. **"Error processing documents"**
   - Ensure PDFs are not password protected
   - Check PDF files are not corrupted
   - Verify sufficient disk space

3. **"Validation failed repeatedly"**
   - Try different model (GPT-4o vs GPT-4o-mini)
   - Reduce max_retries if generation takes too long
   - Check prompt files are properly formatted

4. **"Export failed"**
   - Ensure outputs/ directory is writable
   - Check available disk space
   - Verify all dependencies are installed

### Performance Optimization

1. **Slow generation**:
   - Use GPT-4o-mini for faster processing
   - Reduce context window size in RAG settings
   - Enable auto-retry to avoid manual regeneration

2. **Memory issues**:
   - Process smaller documents
   - Restart Streamlit session
   - Check available system memory

## 📞 Support

For questions, issues, or feature requests:
- Create GitHub issue with detailed description
- Include error logs and system information
- Provide sample files (without sensitive data)

---

**Built with**: Streamlit, LangChain, OpenAI, FAISS, HuggingFace Transformers