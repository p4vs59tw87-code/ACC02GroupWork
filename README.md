# User Guide: EV Valuation Agent

## 1. Who This Product Is For

This tool is designed for equity research analysts covering the **China New Energy Passenger Vehicle (NEPV)** industry. It supports valuation analysis for companies including BYD, Li Auto, XPeng, and NIO.

## 2. How to Use the System

### Step 1: Export Data from WRDS

1. Ensure you have WRDS access configured on your machine.
2. Download the `wrds_export.py` script from the `src/` folder.
3. Update the `operating_data` dictionary in the script with the latest delivery and ASP data from company annual reports.
4. Run the script:
   ```bash
   python wrds_export.py