from fastapi import FastAPI,Path,HTTPException,Query
import json

app = FastAPI()
def load_data():
    with open('patients.json', 'r') as file:
        data = json.load(file)
    return data
@app.get('/')
def hello():
    return {'message':'Patient management system API '}

@app.get('/about')
def about():
    return {'Fully functional api will manage your patient record!'}

@app.get('/view')
def view():
    data = load_data()
    return data
@app.get('/patient/{patient_id}')
def view_patient(patient_id:str=Path(...,description='ID of the patient in the DB',example='P001')):
    #load all the patients data
    data = load_data()
    if patient_id in data:
        return data[patient_id]
    raise HTTPException(status_code=404,detail='Patient Not Found')


@app.get('/sort')
def sort_patients(sortby:str=Query(...,description='sort on the basis of height,weight or bmi'),order:str=Query("asc",description='sort in ascending or descending order')):
    valid_fields = ['height', 'weight', 'bmi']
    if sortby not in valid_fields:
        raise HTTPException(status_code=400,detail=f'Invalid sort field. Choose from {valid_fields}')
    if order not in ['asc','desc']:
        raise HTTPException(status_code=400,detail='Invalid order. Choose "asc" or "desc"')
    data = load_data()
    sort_order =True if order=='desc' else False
    sorted_data = sorted(data.values(), key=lambda x:float( x.get(sortby,0)), reverse= sort_order)
    return sorted_data







