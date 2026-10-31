import os


def remove_between_markers(line, start_marker, end_marker):
    while start_marker in line and end_marker in line:
        start_index = line.find(start_marker)
        end_index = line.find(end_marker)+len(end_marker)
        line = line[:start_index] + line[end_index:]

    return line

def process_file(input_file, output_file, start_marker, end_marker):
    with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
        for line in infile:
            modified_line = remove_between_markers(line, start_marker, end_marker)
            outfile.write(modified_line)

def mod_file(file_path, start_marker, end_marker, chunk_size=65535):
    with open(file_path, 'r+') as file:
        while True:
            content = file.read(chunk_size)
            if not content:
                break

            file.seek(file.tell() - len(content))
            file.write(remove_between_markers(content, start_marker, end_marker))



def delete_file(file_path):
    try:
        os.remove(file_path)
        print(f"File '{file_path}' deleted successfully.")
    except FileNotFoundError:
        print(f"File '{file_path}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

def rename_file(old_name, new_name):
    try:
        os.rename(old_name, new_name)
        print(f"File '{old_name}' renamed to '{new_name}' successfully.")
    except FileNotFoundError:
        print(f"File '{old_name}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")




# 設定輸入和輸出文件，以及要刪除的標記
import sys
input_file_path = ""
output_file_path=""
# 获取命令行参数
# sys.argv[0] 是脚本的名称，后面的元素是传递给脚本的参数
if len(sys.argv) > 2:
    # 第一个参数是脚本的名称，所以参数从第二个开始
    input_file_path = sys.argv[1]
    output_file_path = sys.argv[2]
    print(f"Input argument from command line: {input_file_path}")
else:
    input_file_path = 'C:/Users/yeh_u/Desktop/Aiseed/build-qgroundcontrol-Android_Qt_5_15_2_Clang_Multi_Abi-Debug/Makefile'
    output_file_path = 'C:/Users/yeh_u/Desktop/Aiseed/build-qgroundcontrol-Android_Qt_5_15_2_Clang_Multi_Abi-Debug/ModMakefile'



start_marker = '@echo moc'
end_marker = '&&'

# 執行處理文件的函數
process_file(input_file_path, output_file_path, start_marker, end_marker)

delete_file(input_file_path)

rename_file(output_file_path, input_file_path)