import math

def normal_cdf(x, mu, sigma):
    """Cumulative distribution function for the normal distribution."""
    return 0.5 * (1 + math.erf((x - mu) / (sigma * math.sqrt(2))))

def calculate_p_yes(forecast_mu, strike, direction, sigma=1.0):
    """
    Computes P(Yes) based on a normal distribution around the forecast.
    
    forecast_mu: The forecast value (e.g. 22.5 C)
    strike: The threshold value from Polymarket (e.g. 23.0)
    direction: One of '>=', '>', '<', '<='
    sigma: Uncertainty in degrees (default 1.0)
    """
    if direction in ['>=', '>']:
        # P(X >= strike) = 1 - P(X < strike)
        return 1 - normal_cdf(strike, forecast_mu, sigma)
    elif direction in ['<=', '<']:
        # P(X <= strike)
        return normal_cdf(strike, forecast_mu, sigma)
    return 0.5 # Fallback
