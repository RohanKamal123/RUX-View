def quicksort(arr):
    if len(arr)<=1:
        return arr  
    
    pivot=arr[0]
    
    left=[]
    right=[]
    for i in arr[1:]:
        if i <= pivot:
            left.append(i)
        else:
            right.append(i)
    return quicksort(left) + [pivot] + quicksort(right)
arr1=[2,7,3,4,1,8,3,4,9]

print(quicksort(arr1))

print(quicksort([3,1,5,6,2,9,4,4,5]))
   