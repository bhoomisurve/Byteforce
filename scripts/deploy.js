const { ethers } = require("hardhat");
const fs = require('fs');

async function main() {
    console.log("🚀 Starting deployment...");

    // Get the contract factory
    const MedicineLedger = await ethers.getContractFactory("MedicineLedger");
    
    // Deploy the contract
    console.log("📝 Deploying MedicineLedger contract...");
    const medicineLedger = await MedicineLedger.deploy();
    
    // Wait for deployment to finish
    await medicineLedger.waitForDeployment();
    
    const contractAddress = await medicineLedger.getAddress();
    console.log("✅ MedicineLedger deployed to:", contractAddress);

    // Get the contract ABI
    const contractABI = JSON.parse(medicineLedger.interface.formatJson());
    
    // Save contract info to JSON file
    const contractInfo = {
        address: contractAddress,
        abi: contractABI,
        deployedAt: new Date().toISOString(),
        network: "hardhat",
        contractName: "MedicineLedger"
    };
    
    // Write to file
    fs.writeFileSync('MedicineLedger.json', JSON.stringify(contractInfo, null, 2));
    console.log("📄 Contract ABI and address saved to MedicineLedger.json");
    
    // Test the deployed contract
    console.log("\n🧪 Testing contract functions...");
    
    try {
        // Test getStockCount
        const stockCount = await medicineLedger.getStockCount();
        console.log("✅ getStockCount():", stockCount.toString());
        
        // Test getShortageCount
        const shortageCount = await medicineLedger.getShortageCount();
        console.log("✅ getShortageCount():", shortageCount.toString());
        
        // Test getOrderCount
        const orderCount = await medicineLedger.getOrderCount();
        console.log("✅ getOrderCount():", orderCount.toString());
        
        // Test adding a medicine stock
        console.log("\n📦 Testing addMedicineStock...");
        const tx1 = await medicineLedger.addMedicineStock(
            "Test Pharmacy",
            "Paracetamol",
            100,
            500  // 5.00 in paise
        );
        await tx1.wait();
        console.log("✅ Medicine stock added successfully");
        
        // Test reporting shortage
        console.log("\n⚠️ Testing reportShortage...");
        const tx2 = await medicineLedger.reportShortage(
            "Aspirin",
            "Mumbai"
        );
        await tx2.wait();
        console.log("✅ Shortage reported successfully");
        
        // Test placing order
        console.log("\n📋 Testing placeOrder...");
        const accounts = await ethers.getSigners();
        const tx3 = await medicineLedger.placeOrder(
            "Amoxicillin",
            50,
            accounts[1].address  // Using second account as manufacturer
        );
        await tx3.wait();
        console.log("✅ Order placed successfully");
        
        // Test updating retailer stock
        console.log("\n🏪 Testing updateRetailerStock...");
        const tx4 = await medicineLedger.updateRetailerStock(
            "Paracetamol",
            75
        );
        await tx4.wait();
        console.log("✅ Retailer stock updated successfully");
        
        // Verify counts after operations
        const newStockCount = await medicineLedger.getStockCount();
        const newShortageCount = await medicineLedger.getShortageCount();
        const newOrderCount = await medicineLedger.getOrderCount();
        
        console.log("\n📊 Final counts:");
        console.log("📦 Stock updates:", newStockCount.toString());
        console.log("⚠️ Shortage reports:", newShortageCount.toString());
        console.log("📋 Orders:", newOrderCount.toString());
        
        console.log("\n✅ All tests passed! Contract is ready for use.");
        
    } catch (error) {
        console.error("❌ Contract testing failed:", error.message);
        throw error;
    }
    
    console.log("\n🎉 Deployment completed successfully!");
    console.log("📝 Update your app.py with the new contract address:");
    console.log(`   'contract_address': "${contractAddress}"`);
}

// Error handling
main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error("💥 Deployment failed:", error);
        process.exit(1);
    });
