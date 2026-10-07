# Ollama-GUI

A very simple ollama GUI, implemented using the built-in Python Tkinter library, with no additional dependencies.
Provide you with the simplest possible visual Ollama interface.

## 🚀 Features
### v1.1.0
+ 📁 One file project.
+ 📦 No external dependencies, only **tkinter** which is usually bundled.
+ 🔍 Auto check ollama model list.
+ 🌐 Customizable ollama host support.
+ 💬 Multiple conversations.
+ 📋 Menu bar and right-click menu.
+ 🛑 Stop generating at any time.
### v1.2.0
+ 🗂️ Model Management: Download and Delete Models.
+ 🎨 UI Enhancement: Bubble dialog theme.
+ 📝 Editable Conversation History.
### v1.2.2 
+ 💾 Save and Load Conversation History.

## 📎 Before Start

We need to set up Ollama service first.

Please refer to:   
+ [Ollama](https://ollama.com/)  
+ [Ollama Github](https://github.com/ollama/ollama)

## ⚙️ Run

Choose any way you like:
> **Note: If you are using a Mac and the system version is Sonoma, please refer to the Q&A at the bottom.**

### source code

```
python ollama_gui.py
```

### using pip

```
pip install ollama-gui
ollama-gui
```

## 📋 Q&A

### ImportError: No module named 'Tkinter'

This probably happens because the Tk library is not installed.

For Ubuntu or other distros with Apt:

```
sudo apt-get install python3-tk
```

For Fedora:

```
sudo dnf install python3-tkinter
```

For macOS:

```
brew install python-tk
```

For Windows:

make sure to **check in the Python install the optional feature "tcl/tk and IDLE"**.  

Refer to: https://stackoverflow.com/questions/25905540/importerror-no-module-named-tkinter

## License

This project is licensed under the [MIT License](LICENSE).

