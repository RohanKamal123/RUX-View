import csv
import sys

def fill_na(input_file, output_file):
    with open(input_file, 'r', newline='') as f_in, open(output_file, 'w', newline='') as f_out:
        reader = csv.reader(f_in)
        writer = csv.writer(f_out)
        
        header = next(reader)
        writer.writerow(header)
        
        for row in reader:
            for i in range(1, 7):
                if not row[i]:
                    row[i] = 'N/A'
            writer.writerow(row)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python fill_na.py <input_file> <output_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    fill_na(input_file, output_file)
