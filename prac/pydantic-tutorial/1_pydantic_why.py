def insert_patient_data(name:str,age:int):
    if type(name)==str and type(age)==int:
      print(name)
      print(age)
      print("Data inserted successfully")
    else:
      raise TypeError("Invalid data types for name or age") 
    
def update(name:str,age:int):
    if type(name)==str and type(age)==int:
      print(name)
      print(age)
      print("Data inserted successfully")
    else:
      raise TypeError("Invalid data types for name or age") 
insert_patient_data('John Doe', 30)


