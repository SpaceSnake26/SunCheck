1. check om api for each market (8 cities)
2. check polymarket for each market
3. check if there is an arbitrage opportunity
criteria: step 1, threshold of max 15% from highest value in the om-api to next possible full integer
step 2, integer from step1 is available to bet on on on polymarket
step 3, search for bet and shareprice to buy 'yes' on this bet
step 4, if shareprice on pm is < 0.18 USD --> valid opportunity
4. if there is an arbitrage opportunity, display the arbitrage opportunity on the frontend
5. if there is no arbitrage opportunity, display nothing but keep checking for arbitrage opportunities and display log in the 'system logs' with reason why the opps is not available