// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract MedicineLedger {
    // Structs
    struct StockUpdate {
        string pharmacy;
        string medicine;
        uint256 quantity;
        uint256 price;
        uint256 timestamp;
        address updatedBy;
    }
    
    struct ShortageReport {
        string medicine;
        string location;
        uint256 timestamp;
        address reportedBy;
    }
    
    struct Order {
        string medicine;
        uint256 quantity;
        address retailer;
        address manufacturer;
        string status;
        uint256 timestamp;
    }
    
    // State variables
    mapping(uint256 => StockUpdate) public stockUpdates;
    mapping(uint256 => ShortageReport) public shortageReports;
    mapping(uint256 => Order) public orders;
    
    // Retailer stock tracking
    mapping(address => mapping(string => uint256)) public retailerStocks;
    
    uint256 public stockCount;
    uint256 public shortageCount;
    uint256 public orderCount;
    
    // Events
    event StockAdded(string pharmacy, string medicine, uint256 quantity, uint256 price, address updatedBy);
    event ShortageReported(string medicine, string location, address reportedBy);
    event OrderPlaced(string medicine, uint256 quantity, address retailer, address manufacturer);
    event RetailerStockUpdated(address retailer, string medicine, uint256 newStock);
    
    // Modifiers
    modifier onlyValidAddress() {
        require(msg.sender != address(0), "Invalid address");
        _;
    }
    
    // Constructor
    constructor() {
        stockCount = 0;
        shortageCount = 0;
        orderCount = 0;
    }
    
    // Functions that your Python code is calling
    function addMedicineStock(
        string memory _pharmacy,
        string memory _medicine,
        uint256 _quantity,
        uint256 _price
    ) public onlyValidAddress {
        stockUpdates[stockCount] = StockUpdate({
            pharmacy: _pharmacy,
            medicine: _medicine,
            quantity: _quantity,
            price: _price,
            timestamp: block.timestamp,
            updatedBy: msg.sender
        });
        
        stockCount++;
        emit StockAdded(_pharmacy, _medicine, _quantity, _price, msg.sender);
    }
    
    function reportShortage(
        string memory _medicine,
        string memory _location
    ) public onlyValidAddress {
        shortageReports[shortageCount] = ShortageReport({
            medicine: _medicine,
            location: _location,
            timestamp: block.timestamp,
            reportedBy: msg.sender
        });
        
        shortageCount++;
        emit ShortageReported(_medicine, _location, msg.sender);
    }
    
    function placeOrder(
        string memory _medicine,
        uint256 _quantity,
        address _manufacturer
    ) public onlyValidAddress {
        orders[orderCount] = Order({
            medicine: _medicine,
            quantity: _quantity,
            retailer: msg.sender,
            manufacturer: _manufacturer,
            status: "pending",
            timestamp: block.timestamp
        });
        
        orderCount++;
        emit OrderPlaced(_medicine, _quantity, msg.sender, _manufacturer);
    }
    
    function updateRetailerStock(
        string memory _medicine,
        uint256 _newStock
    ) public onlyValidAddress {
        retailerStocks[msg.sender][_medicine] = _newStock;
        emit RetailerStockUpdated(msg.sender, _medicine, _newStock);
    }
    
    function updateOrderStatus(
        uint256 _orderId,
        string memory _newStatus
    ) public onlyValidAddress {
        require(_orderId < orderCount, "Order does not exist");
        
        Order storage order = orders[_orderId];
        require(
            msg.sender == order.retailer || msg.sender == order.manufacturer,
            "Not authorized to update this order"
        );
        
        order.status = _newStatus;
    }
    
    // View functions
    function getStockCount() public view returns (uint256) {
        return stockCount;
    }
    
    function getShortageCount() public view returns (uint256) {
        return shortageCount;
    }
    
    function getOrderCount() public view returns (uint256) {
        return orderCount;
    }
    
    function getOrder(uint256 _orderId) public view returns (
        string memory medicine,
        uint256 quantity,
        address retailer,
        address manufacturer,
        string memory status
    ) {
        require(_orderId < orderCount, "Order does not exist");
        Order memory order = orders[_orderId];
        return (order.medicine, order.quantity, order.retailer, order.manufacturer, order.status);
    }
    
    function getStockUpdate(uint256 _stockId) public view returns (
        string memory pharmacy,
        string memory medicine,
        uint256 quantity,
        uint256 price,
        uint256 timestamp,
        address updatedBy
    ) {
        require(_stockId < stockCount, "Stock update does not exist");
        StockUpdate memory stock = stockUpdates[_stockId];
        return (stock.pharmacy, stock.medicine, stock.quantity, stock.price, stock.timestamp, stock.updatedBy);
    }
    
    function getShortageReport(uint256 _reportId) public view returns (
        string memory medicine,
        string memory location,
        uint256 timestamp,
        address reportedBy
    ) {
        require(_reportId < shortageCount, "Shortage report does not exist");
        ShortageReport memory report = shortageReports[_reportId];
        return (report.medicine, report.location, report.timestamp, report.reportedBy);
    }
    
    function getRetailerStock(address _retailer, string memory _medicine) public view returns (uint256) {
        return retailerStocks[_retailer][_medicine];
    }
    
    // Utility functions
    function getAllStocks() public view returns (StockUpdate[] memory) {
        StockUpdate[] memory allStocks = new StockUpdate[](stockCount);
        for (uint256 i = 0; i < stockCount; i++) {
            allStocks[i] = stockUpdates[i];
        }
        return allStocks;
    }
    
    function getAllShortages() public view returns (ShortageReport[] memory) {
        ShortageReport[] memory allShortages = new ShortageReport[](shortageCount);
        for (uint256 i = 0; i < shortageCount; i++) {
            allShortages[i] = shortageReports[i];
        }
        return allShortages;
    }
    
    function getAllOrders() public view returns (Order[] memory) {
        Order[] memory allOrders = new Order[](orderCount);
        for (uint256 i = 0; i < orderCount; i++) {
            allOrders[i] = orders[i];
        }
        return allOrders;
    }
    
    // Emergency functions
    function emergencyPause() public {
        // Could add pause functionality if needed
    }
    
    function getContractInfo() public pure returns (string memory) {
        return "MedicineLedger v1.0 - Healthcare Supply Chain Management";
    }
}