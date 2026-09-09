from detector import detect_allergens

result = detect_allergens("test_images/label5.jpg", ["susu", "kacang tanah"])
print(result)