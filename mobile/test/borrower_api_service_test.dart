import "package:fing_mobile/app/borrowers/borrower_api_service.dart";
import "package:flutter_test/flutter_test.dart";

void main() {
  test("searchBorrowers maps API items", () async {
    String? capturedPath;
    final BorrowerApiService service = BorrowerApiService(
      getJson: (String path) async {
        capturedPath = path;
        return <String, dynamic>{
          "items": <Map<String, dynamic>>[
            <String, dynamic>{
              "id": "b-1",
              "fullName": "Asha Kumar",
              "phoneNumber": "9876543210",
              "status": "ACTIVE",
            }
          ]
        };
      },
    );

    final result = await service.searchBorrowers(fullName: "Asha");

    expect(capturedPath, "/borrowers?fullName=Asha");
    expect(result.items, hasLength(1));
    expect(result.items.first.fullName, "Asha Kumar");
  });

  test("getBorrowerById maps borrower payload", () async {
    String? capturedPath;
    final BorrowerApiService service = BorrowerApiService(
      getJson: (String path) async {
        capturedPath = path;
        return <String, dynamic>{
          "id": "b-2",
          "fullName": "Rahul Das",
          "phoneNumber": "9000000000",
          "status": "BLOCKED",
        };
      },
    );

    final borrower = await service.getBorrowerById("b-2");

    expect(capturedPath, "/borrowers/b-2");
    expect(borrower.id, "b-2");
    expect(borrower.status, "BLOCKED");
  });
}
