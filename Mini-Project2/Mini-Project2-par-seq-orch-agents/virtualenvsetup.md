### Python Virtual Environment Setup

```bash
python -m venv myvirtualenv

cd myvirtualenv\Scripts

.\Activate

cd ..

pip install -r requirements.txt

```

### Adding Virtual Environment to Jupyter Notebooks

```bash
ipython kernel install --user --name=myvirtualenv --display-name "Python (myvirtualenv)"
```