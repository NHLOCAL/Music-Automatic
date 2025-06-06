@echo off

npx repomix -i "data/**,logs/**,run_repomix.bat,experiments/**,repomix-output.*,app.py,create_ml_dataset.py,similarity_model/**,legacy/**,Notes.txt" --style markdown --remove-comments --remove-empty-lines