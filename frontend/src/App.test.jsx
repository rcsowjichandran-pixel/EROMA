import React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import App, { BankOfferStrip, CartCouponOffers, openWhatsAppChat, ProductColourPreview, ProductGrid } from './App'

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

describe('storefront flows', () => {
  const sofa = {...product, status: 'active'}
  const table = {...product, id: 42, name: 'Oak table', regular_price: '0', status: 'active'}

  function mockStore(endpoints = {}) {
    vi.stubGlobal('matchMedia', () => ({matches: false}))
    vi.stubGlobal('scrollTo', vi.fn())
    vi.stubGlobal('fetch', vi.fn(async url => {
      const {pathname, search} = new URL(url)
      const route = pathname.replace(/^\/api/, '') + search
      const data = endpoints[route] ?? (route === '/products/' ? [sofa, table] : [])
      return {ok: true, status: 200, json: async () => await data}
    }))
  }

  afterEach(() => {
    localStorage.clear()
    vi.unstubAllGlobals()
  })

  it('filters Spot Deals to products with a markdown', async () => {
    mockStore()
    render(<App/>)
    await screen.findByText('Up to 9% off')
    fireEvent.click(screen.getByRole('button', {name: 'Shop spot deals'}))
    expect(screen.getByRole('checkbox', {name: 'On sale'})).toBeChecked()
    expect(screen.getByText('1 piece found')).toBeInTheDocument()
    expect(screen.queryByRole('button', {name: 'Add Oak table to bag'})).toBeNull()
  })

  it('shows progress and then the result count for a submitted search', async () => {
    let finishSearch
    mockStore({'/products/?search=sofa': new Promise(resolve => {finishSearch = resolve})})
    render(<App/>)
    const search = screen.getByRole('textbox', {name: 'Search furniture'})
    fireEvent.change(search, {target: {value: 'sofa'}})
    fireEvent.submit(screen.getByRole('search'))
    expect(screen.getAllByText(/Searching for sofa/).length).toBeGreaterThan(0)
    finishSearch([sofa])
    expect(await screen.findByText('1 piece found for sofa')).toBeInTheDocument()
  })

  it('fills signed-in checkout from the default saved address', async () => {
    localStorage.setItem('sofalux_access', 'test-token')
    localStorage.setItem('eroma_cart_user_1', JSON.stringify([{...sofa, quantity: 1}]))
    mockStore({
      '/me/': {id: 1, username: 'shopper'},
      '/profile/': {first_name: 'Luna', email: 'luna@example.com', phone: '9999999999'},
      '/addresses/': [{id: 1, label: 'Home', full_name: 'Luna Shopper', city: 'Mumbai', address: '10 Test Street', phone: '9876543210', postal_code: '400001', is_default: true}],
    })
    render(<App/>)
    fireEvent.click(await screen.findByRole('button', {name: 'Shopping bag: 1 items'}))
    expect(await screen.findByDisplayValue('10 Test Street')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Email')).toHaveValue('luna@example.com')
    expect(screen.getByPlaceholderText('Phone')).toHaveValue('9876543210')
    expect(screen.getByPlaceholderText('Postal code')).toHaveValue('400001')
  })
})

it('opens the catalog when the bank name is clicked and exposes each offer once', () => {
  const onShop = vi.fn()
  render(<BankOfferStrip onShop={onShop}/>)
  const axisOffer = screen.getByRole('button', {name: /Axis Bank/})
  fireEvent.click(axisOffer.querySelector('b'))
  expect(onShop).toHaveBeenCalledOnce()
})

describe('ProductColourPreview', () => {
  it('previews the selected upholstery on the model photo and prefers a matching variant', () => {
    const sofa = {...product, image_url: '/media/3_Seater.jpeg', images: [{image: '/media/luna-olive.jpg', alt_text: 'Colour: Olive'}]}
    function DetailMedia() {
      const [colour, setColour] = React.useState('Ivory')
      return <ProductColourPreview product={sofa} photo={sofa.image_url} colour={colour} onChange={setColour}/>
    }

    render(<DetailMedia />)
    expect(screen.getByAltText('Luna sofa')).toHaveAttribute('src', sofa.image_url)
    expect(screen.queryByText('Approximate upholstery colour')).toBeNull()
    fireEvent.click(screen.getByRole('button', {name: 'Choose Charcoal'}))
    expect(screen.getByRole('button', {name: 'Choose Charcoal'})).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByAltText('Luna sofa, approximate Charcoal upholstery preview')).toHaveAttribute('src', sofa.image_url)
    fireEvent.click(screen.getByRole('button', {name: 'Show original photo'}))
    expect(screen.getByAltText('Luna sofa')).toHaveAttribute('src', sofa.image_url)
    expect(screen.getByRole('button', {name: 'Choose Charcoal'})).toHaveAttribute('aria-pressed', 'true')

    fireEvent.click(screen.getByRole('button', {name: 'Choose Olive'}))
    expect(screen.getByAltText('Luna sofa in Olive')).toHaveAttribute('src', '/media/luna-olive.jpg')
    expect(screen.queryByText('Approximate upholstery colour')).toBeNull()
  })

  it('uses a different photo and upholstery outline for a different model', () => {
    const onChange = vi.fn()
    const {container, rerender} = render(<ProductColourPreview product={product} photo="/media/3_Seater.jpeg" colour="Olive" onChange={onChange}/>)
    fireEvent.click(screen.getByRole('button', {name: 'Choose Olive'}))
    const firstOutline = container.querySelector('.sofa-photo-tint').style.clipPath
    rerender(<ProductColourPreview product={{...product, name: 'L-shaped sofa'}} photo="/media/L_shape.jpeg" colour="Olive" onChange={onChange}/>)
    expect(screen.getByAltText('L-shaped sofa')).toHaveAttribute('src', '/media/L_shape.jpeg')
    fireEvent.click(screen.getByRole('button', {name: 'Choose Olive'}))
    expect(screen.getByAltText('L-shaped sofa, approximate Olive upholstery preview')).toHaveAttribute('src', '/media/L_shape.jpeg')
    expect(container.querySelector('.sofa-photo-tint').style.clipPath).not.toBe(firstOutline)
  })
})

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
