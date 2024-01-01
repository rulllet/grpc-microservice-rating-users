@echo off

echo [1/2] Install packege...
pip install -r requirements.txt

echo [2/2]Generating proto...
python -m grpc_tools.protoc -I./ --python_out=. --pyi_out=. --grpc_python_out=. rating.proto

echo RUN!
python main.py