# Contributing to CROT DALAM

Thank you for your interest in contributing to CROT DALAM! This document provides guidelines for contributing.

## 🚀 Getting Started

### Development Setup

1. **Clone the repository**

```bash
git clone https://github.com/Masriyan/CrotDalam.git
cd CrotDalam
```

2. **Create a virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
playwright install chromium
```

4. **Run the tool**

```bash
# CLI mode
python -m crot_dalam.cli search "test" --limit 5

# GUI mode
python -m crot_dalam.cli gui
```

## 📝 How to Contribute

### Reporting Bugs

- Use the GitHub Issues tab
- Include reproduction steps
- Attach error messages and logs
- Mention your OS and Python version

### Suggesting Features

- Open an issue with the `enhancement` label
- Describe the use case
- Explain how it improves OSINT workflows

### Code Contributions

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test thoroughly
5. Commit with clear messages (`git commit -m 'Add amazing feature'`)
6. Push to your fork (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## 🎨 Code Style

- Follow PEP 8 guidelines
- Use type hints where possible
- Write docstrings for functions and classes
- Keep functions focused and modular

## 🔧 Areas for Contribution

### High Priority

- Additional language support for risk terms
- Improved selectors for TikTok UI changes
- Performance optimizations
- Documentation improvements

### New Features

- Additional export formats (PDF)
- Integration with threat intel platforms
- Scheduled monitoring automation
- Mobile app integration

### Risk Terms

Add new scam/phishing terms for your language:

```python
# In crot_dalam/core/risk_analyzer.py
RISK_TERMS["your_language"] = {
    "category": [
        ("term", weight),
    ],
}
```

## 📜 Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Use responsibly and ethically

## ⚖️ License

By contributing, you agree that your contributions will be licensed under the MIT License.
