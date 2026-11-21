import React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { CartCouponOffers, openWhatsAppChat, ProductGrid } from './App'

const product = {
  id: 41,
  name: 'Luna sofa',
  price: '25000.00',
  regular_price: '27500.00',
  stock: 4,
  material: 'Velvet upholstery',
  image_url: '/media/luna-sofa.jpg',
  review_count: 0,
  collective_review_count: 0,
}

afterEach(cleanup)

describe('ProductGrid', () => {
  it('shows the product price and calls the product detail handler', () => {
    const onOpen = vi.fn()
    render(<ProductGrid products={[product]} onOpen={onOpen} onAdd={vi.fn()} />)

    expect(screen.getByText('Luna sofa')).toBeInTheDocument()
    expect(screen.getByText('₹25,000')).toBeInTheDocument()
    fireEvent.click(screen.getByAltText('Luna sofa'))
    expect(onOpen).toHaveBeenCalledWith(product)
  })

  it('adds an in-stock product and gives temporary added feedback', () => {
    const onAdd = vi.fn()
    render(<ProductGrid products={[product]} onOpen={vi.fn()} onAdd={onAdd} />)

    fireEvent.click(screen.getByRole('button', { name: 'Add Luna sofa to bag' }))
    expect(onAdd).toHaveBeenCalledWith(product)
    expect(screen.getByRole('button', { name: /Luna sofa, added to bag/i })).toHaveTextContent('Added to bag')
  })

  it('prevents adding an out-of-stock item or exceeding available stock', () => {
    const { rerender } = render(<ProductGrid products={[{ ...product, stock: 0 }]} onOpen={vi.fn()} onAdd={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Add Luna sofa to bag' })).toBeDisabled()

    rerender(<ProductGrid products={[product]} onOpen={vi.fn()} onAdd={vi.fn()} cart={[{ id: product.id, quantity: 4 }]} />)
    expect(screen.getByRole('button', { name: 'Add Luna sofa to bag' })).toBeDisabled()
    expect(screen.getByText('Stock limit reached')).toBeInTheDocument()
  })

  it('calls the wishlist handler when the customer toggles the heart', () => {
    const onWishlist = vi.fn()
    render(<ProductGrid products={[product]} onOpen={vi.fn()} onAdd={vi.fn()} onWishlist={onWishlist} />)
    fireEvent.click(screen.getByRole('button', { name: 'Add Luna sofa to wishlist' }))
    expect(onWishlist).toHaveBeenCalledWith(product)
  })
})

describe('CartCouponOffers', () => {
  it('shows available coupon details and applies the selected code', () => {
    const onApply = vi.fn()
    render(<CartCouponOffers
      coupons={[{ code: 'HOME10', discount_type: 'percent', discount_value: 10, minimum_order: 5000, description: 'Furniture offer' }]}
      categories={[]}
      selectedCode=""
      onApply={onApply}
    />)

    expect(screen.getByText('HOME10')).toBeInTheDocument()
    expect(screen.getByText(/10% off · Min\. ₹5,000/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))
    expect(onApply).toHaveBeenCalledWith('HOME10')
  })
})

describe('WhatsApp customer contact', () => {
  it('opens the configured EROMA number with the customer message prefilled', () => {
    const openWindow = vi.fn()
    expect(openWhatsAppChat('+91 88388 16692', 'I need help with a sofa', openWindow)).toBe(true)
    expect(openWindow).toHaveBeenCalledWith(
      'https://wa.me/918838816692?text=I%20need%20help%20with%20a%20sofa',
      '_blank',
      'noopener,noreferrer',
    )
  })
})
