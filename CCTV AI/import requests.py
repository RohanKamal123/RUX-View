import requests

url = "https://jsonplaceholder.typicode.com/users"
params = {'_page': 1, '_limit': 5}   # change page and limit as needed

response = requests.get(url, params=params)

print('Final URL:', response.url)
print('Status Code:', response.status_code)

response.raise_for_status()

data = response.json()

print(f"Total users fetched: {len(data)}\n")

for user in data:
    print(user['email'], "-", user['name'])