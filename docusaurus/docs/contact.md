---
title: Contact & Support
description: Get help and support for v8x
---

# Contact & Support

Get help, report issues, or connect with the Vantage Compute community.

## Stay Updated

### 📢 Announcements
- **GitHub Releases**: Watch the repository for release notifications
- **GitHub Discussions**: Follow announcement category
- **Company Blog**: [vantagecompute.ai/blog](https://vantagecompute.ai/blog)

### 🔔 Notifications
Configure GitHub notifications for:
- New releases
- Issue mentions
- Discussion replies
- PR Review/Contribution


### 💬 Community Support

#### GitHub Discussions
**Best for**: General questions, usage help, feature discussions

- **URL**: [github.com/vantagecompute/v8x/discussions](https://github.com/vantagecompute/v8xdiscussions)
- **Categories**:
  - **Q&A**: Usage questions and help
  - **Ideas**: Feature requests and suggestions
  - **Show and tell**: Share your deployments
  - **General**: General discussions

#### GitHub Issues
**Best for**: Bug reports, specific problems, feature requests

- **URL**: [github.com/vantagecompute/v8x/issues](https://github.com/vantagecompute/v8x/issues)
- **Templates**: This project provides issue templates for:
  - Bug reports
  - Feature requests
  - Documentation improvements

### 🚀 Quick Help

#### Before Asking for Help

1. **Check documentation**: Search our faq for your issue
2. **Review troubleshooting**: Common issues are covered in the [troubleshooting guide](./troubleshooting)
3. **Search existing issues**: Your question might already be answered
4. **Try alternate profiles**: Reproduce with a fresh profile

#### When Asking for Help

Include this information:

```bash
# System information
uname -a                    # OS and kernel
python3 --version          # Python version

# v8x information
v8x --help
v8x version
```

## Bug Reports

### 🐛 Reporting Bugs

**Use**: [GitHub Issues](https://github.com/vantagecompute/v8x/issues/new/choose)

**Include**:

1. **Clear description**: What you expected vs what happened
2. **Steps to reproduce**: Minimal steps to reproduce the issue
3. **Environment**: OS, Python, LXD versions
4. **Logs**: Error messages and relevant log files
5. **Workarounds**: Any temporary solutions you've found

**Example Bug Report**:

```markdown
## Bug Description
Device login stalls after code display

## Steps to Reproduce
1. `uv run v8x login`
2. No browser prompt after code output

## Environment
- OS: Ubuntu 24.04 LTS
- Python: 3.12.x
- UV: 0.4.x

## Observed Behavior
No polling progress; login never completes.
```

### 🔍 Security Issues

For security vulnerabilities:
- **Email**: security@vantagecompute.ai
- **Include**: Detailed description and impact assessment
- **Response time**: We aim to respond within 24 hours

## Feature Requests

### 💡 Suggesting Features

**Use**: [GitHub Discussions - Ideas](https://github.com/vantagecompute/v8x/discussions/categories/ideas)

**Include**:

1. **Use case**: Why you need this feature
2. **Proposed solution**: How you think it should work
3. **Alternatives**: Other solutions you've considered
4. **Examples**: Similar features in other tools

## Commercial Support

### 🏢 Enterprise Support

For commercial deployments and enterprise support:

- **Company**: Vantage Compute
- **Website**: https://vantagecompute.ai
- **Email**: support@vantagecompute.ai

**Services**:

- Advisory & enablement
- Platform integration
- Performance analysis
- Priority support and fixes
- Training and professional services

### 📈 Consulting Services

- **HPC Architecture Design**: Cluster planning and optimization
- **Migration Services**: Moving from other schedulers to Slurm
- **Performance Tuning**: Optimizing Slurm for your workloads
- **Custom Development**: Feature development and integration

## Contributing

### 🤝 Get Involved

Want to contribute? We welcome:
- **Code contributions**: Bug fixes, new features
- **Documentation**: Improvements and examples
- **Testing**: Testing new features and releases
- **Community support**: Helping other users

**Start here**: [Contributing Guide](./contributing)

### 👥 Maintainers

- **Core Team**: Vantage Compute team
- **Lead Maintainer**: Available via GitHub
- **Community**: Active contributors and users

## Response Times

### Community Support

- **GitHub Discussions**: Usually within 1-2 days
- **GitHub Issues**: Usually within 2-3 days
- **Documentation**: Updates within 1 week

### Commercial Support

- **Critical Issues**: Within 4 hours
- **Standard Issues**: Within 1 business day
- **Feature Requests**: Within 1 week

**We're here to help!** Don't hesitate to reach out if you have questions or need assistance with v8x.
