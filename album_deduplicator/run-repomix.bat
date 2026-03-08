@echo off

npx repomix -i "data/**,logs/**,run-repomix.bat,experiments/**,repomix-output.*,create_ml_dataset.py,similarity_model/**,legacy/**,Notes.txt,docs/**,tests/**,**/frontend/package-lock.json," --style markdown --remove-comments --remove-empty-lines
