import React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import App, { BankOfferStrip, CartCouponOffers, getCheckoutAmounts, ProductColourPreview, ProductGrid } from './App'

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

it('uses paise for totals and does not add included GST again', () => {
  expect(getCheckoutAmounts([{price:'1000.01',quantity:2}], '200.01', {})).toEqual({
    total:2000.02,gstRate:18,taxAmount:274.58,deliveryFee:999,payableTotal:2799.01,
  })
})

describe('storefront flows', () => {
  const sofa = {...product, status: 'active'}
  const table = {...product, id: 42, name: 'Oak table', regular_price: '0', status: 'active'}

  function mockStore(endpoints = {}) {
    vi.stubGlobal('matchMedia', () => ({matches: false}))
    vi.stubGlobal('scrollTo', vi.fn())
    vi.stubGlobal('fetch', vi.fn(async (url, options) => {
      const {pathname, search} = new URL(url)
      const route = pathname.replace(/^\/api/, '') + search
      const endpoint = endpoints[route]
      const data = typeof endpoint==='function' ? await endpoint(options) : endpoint ?? (route === '/products/' ? [sofa, table] : [])
      return {ok: true, status: 200, json: async () => await data}
    }))
  }

  afterEach(() => {
    localStorage.clear()
    vi.unstubAllGlobals()
  })

  it('links the floating WhatsApp button and Contact Us directly to WhatsApp Web', () => {
    mockStore()
    render(<App/>)
    const floatingLink = screen.getByRole('link', {name: 'Open EROMA on WhatsApp Web'})
    expect(floatingLink.getAttribute('href')).toMatch(/^https:\/\/web\.whatsapp\.com\/send\?phone=[0-9]+$/)
    expect(floatingLink).toHaveAttribute('target', '_blank')
    fireEvent.click(screen.getByRole('button', {name: 'Contact Us', exact: true}))
    expect(screen.getByRole('link', {name: 'Chat with EROMA'})).toHaveAttribute('href', floatingLink.getAttribute('href'))
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

  it('hides the Back button when returning home through the logo', async () => {
    mockStore()
    render(<App/>)
    const backButton = {name: 'Back', exact: true}
    expect(screen.queryByRole('button', backButton)).not.toBeInTheDocument()
    fireEvent.click(await screen.findByRole('button', {name: 'Shop All'}))
    expect(screen.getByRole('button', backButton)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', {name: 'EROMA home'}))
    expect(screen.queryByRole('button', backButton)).not.toBeInTheDocument()
  })

  it('recommends in-stock furniture from browsing history and wishlist preferences', async () => {
    const viewed = {...sofa, category: 1}
    const similar = {...sofa, id: 43, name: 'Cedar sofa', category: 1}
    const unavailable = {...similar, id: 44, name: 'Birch sofa', stock: 0}
    const saved = {...table, category: 2, material: 'Oak'}
    const savedMatch = {...saved, id: 45, name: 'Oak side table'}
    const unrelated = {...table, id: 46, name: 'Metal lamp', category: 3, material: 'Steel'}
    localStorage.setItem('sofalux_access', 'test-token')
    mockStore({
      '/me/': {id: 1, username: 'shopper'},
      '/products/': [viewed, similar, unavailable, saved, savedMatch, unrelated],
      '/wishlist/': [{id: 1, product: saved}],
    })
    render(<App/>)
    const shelf = {name: 'Recommended for you'}
    expect(within(await screen.findByRole('region', shelf)).getByAltText('Oak side table')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', {name: 'Shop All'}))
    fireEvent.click(await screen.findByAltText('Luna sofa'))
    fireEvent.click(screen.getByRole('button', {name: 'EROMA home'}))
    const recommendations = within(screen.getByRole('region', shelf))
    expect(recommendations.getAllByRole('img').map(image=>image.alt)).toEqual(['Oak side table', 'Cedar sofa'])
    expect(JSON.parse(localStorage.getItem('eroma_recently_viewed_user_1'))[0].id).toBe(viewed.id)
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
    expect(screen.getByText('Estimated delivery')).toBeInTheDocument()
    expect(screen.getByText(/5–10 calendar days/)).toBeInTheDocument()
  })

  it('confirms coupon savings beside the apply controls', async () => {
    localStorage.setItem('sofalux_access', 'test-token')
    localStorage.setItem('eroma_cart_user_1', JSON.stringify([{...sofa, quantity: 1}]))
    mockStore({
      '/me/': {id: 1, username: 'shopper'},
      '/coupons/available/': [{code: 'HOME600'}],
      '/coupons/validate/': {code: 'HOME600', discount: 600},
    })
    render(<App/>)
    fireEvent.click(await screen.findByRole('button', {name: 'Shopping bag: 1 items'}))
    fireEvent.click(await screen.findByRole('button', {name: 'HOME600'}))
    const message = await screen.findByText(/HOME600 applied. You saved/)
    expect(message).toHaveClass('coupon-applied-message')
    expect(message.previousElementSibling).toContainElement(screen.getByRole('button', {name: 'Apply coupon'}))
    expect(screen.getByRole('button', {name: 'HOME600'})).toHaveAttribute('aria-pressed', 'true')
  })

  it('adds the chosen quantity from product details and goes back through the visited pages', async () => {
    mockStore({'/products/': [{...sofa, stock: 10}, table]})
    render(<App/>)
    fireEvent.click(screen.getByRole('button', {name: 'Shop All'}))
    fireEvent.click(await screen.findByAltText('Luna sofa'))

    expect(screen.getByText('10 available')).toBeInTheDocument()
    const increase = screen.getByRole('button', {name: 'Increase quantity'})
    const decrease = screen.getByRole('button', {name: 'Decrease quantity'})
    expect(screen.getByRole('group', {name: 'Quantity'}).querySelector('output')).toHaveTextContent('0')
    expect(screen.getByRole('button', {name: 'Add to bag'})).toBeDisabled()
    fireEvent.click(increase)
    expect(screen.getByRole('group', {name: 'Quantity'}).querySelector('output')).toHaveTextContent('1')
    expect(screen.getByText('9 available after adding')).toBeInTheDocument()
    fireEvent.click(decrease)
    expect(screen.getByText('10 available')).toBeInTheDocument()
    for (let step=0; step<4; step++) fireEvent.click(increase)
    expect(screen.getByText('6 available after adding')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', {name: 'Decrease quantity'}))
    expect(screen.getByText('7 available after adding')).toBeInTheDocument()
    fireEvent.click(increase)
    vi.useFakeTimers()
    try {
      fireEvent.click(screen.getByRole('button', {name: 'Add to bag'}))
      expect(screen.getByText(/Added to your bag/)).toBeInTheDocument()
      act(()=>vi.advanceTimersByTime(4000))
      expect(screen.queryByText(/Added to your bag/)).toBeNull()
    } finally {
      vi.useRealTimers()
    }
    expect(screen.getByText('6 available')).toBeInTheDocument()
    expect(screen.getByRole('button', {name: 'Shopping bag: 4 items'})).toBeInTheDocument()
    for (let step=0; step<6; step++) fireEvent.click(increase)
    expect(screen.getByRole('button', {name: 'Increase quantity'})).toBeDisabled()
    fireEvent.click(screen.getByRole('button', {name: 'Buy now'}))
    expect(screen.getByRole('button', {name: 'Shopping bag: 10 items'})).toBeInTheDocument()
    expect(screen.getByRole('heading', {name: /your shopping bag/i})).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', {name: 'Back', exact: true}))
    expect(screen.getByRole('heading', {name: 'Luna sofa', level: 1})).toBeInTheDocument()
    expect(screen.getByText('0 available')).toBeInTheDocument()
    expect(screen.getByRole('button', {name: 'Buy now'})).toBeDisabled()
    fireEvent.click(screen.getByRole('button', {name: 'Back', exact: true}))
    expect(screen.getByRole('heading', {name: /find your favourite/i})).toBeInTheDocument()
  })

  it('shows the catalog description and related products while keeping product back history', async () => {
    const source = {...sofa, category: 2, description: 'A compact sofa for a smaller room.\n\nPair with a soft rug.', dimensions: '150 x 85 x 80 cm'}
    const related = {...sofa, id: 43, name: 'Rowan sofa', category: 3, description: 'A deeper sofa with soft cushions.', image_url: '/media/rowan.jpg'}
    mockStore({
      '/products/': [source, related, {...table, category: 4}],
      '/categories/': [{id: 1, name: 'Sofas', parent: null}, {id: 2, name: 'Two-seater Sofas', parent: 1},
        {id: 3, name: 'Three-seater Sofas', parent: 1}, {id: 4, name: 'Tables', parent: null}],
    })
    render(<App/>)
    fireEvent.click(screen.getByRole('button', {name: 'Shop All'}))
    fireEvent.click(await screen.findByAltText('Luna sofa'))
    const description = screen.getByRole('region', {name: 'Product description'})
    expect([...description.querySelectorAll('p')].map(paragraph=>paragraph.textContent)).toEqual(source.description.split('\n\n'))
    expect(screen.getByText(source.dimensions)).toBeInTheDocument()
    const suggestions = screen.getByRole('region', {name: 'Related products'})
    expect(suggestions).toHaveTextContent('Rowan sofa')
    expect(suggestions).not.toHaveTextContent('Oak table')
    fireEvent.click(suggestions.querySelector('img'))
    expect(screen.getByRole('heading', {name: 'Rowan sofa', level: 1})).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', {name: 'Back', exact: true}))
    expect(screen.getByRole('heading', {name: 'Luna sofa', level: 1})).toBeInTheDocument()
  })

  it('shows the reduced stock after a confirmed COD order, even if the stock refresh fails', async () => {
    localStorage.setItem('sofalux_access', 'test-token')
    const item = {...sofa, stock: 10}
    const order = {id: 1, items: [{id: 1, product: item.id, product_name: item.name, quantity: 4}]}
    let sold = false
    mockStore({
      '/products/': () => {if (sold) throw new Error('Offline');return [item]},
      '/me/': {id: 1, username: 'shopper'},
      '/profile/': {email: 'luna@example.com'},
      '/addresses/': [{id: 1, full_name: 'Luna Shopper', city: 'Mumbai', address: '10 Test Street', phone: '9876543210', postal_code: '400001', is_default: true}],
      '/orders/': options => {if (options.method==='POST') {sold=true;return order} return [order]},
    })
    render(<App/>)
    fireEvent.click(screen.getByRole('button', {name: 'Shop All'}))
    fireEvent.click(await screen.findByAltText('Luna sofa'))
    const increase = screen.getByRole('button', {name: 'Increase quantity'})
    for (let step=0;step<4;step++) fireEvent.click(increase)
    fireEvent.click(screen.getByRole('button', {name: 'Buy now'}))
    expect(await screen.findByDisplayValue('10 Test Street')).toBeInTheDocument()
    fireEvent.submit(screen.getByRole('button', {name: 'Place COD order'}).closest('form'))
    await screen.findByText(/Order #1 placed/)
    fireEvent.click(screen.getByRole('button', {name: 'Back', exact: true}))
    fireEvent.click(screen.getByRole('button', {name: 'Back', exact: true}))
    expect(screen.getByText('6 available')).toBeInTheDocument()
  })

  it.each([
    ['razorpay', 'Pay securely with Razorpay', 'Payment failed'],
    ['razorpay_emi', 'Continue to card EMI', 'Card EMI payment failed'],
  ])('keeps the bag and reports a verified failure for %s', async (method, buttonLabel, failure) => {
    localStorage.setItem('sofalux_access', 'test-token')
    localStorage.setItem('eroma_cart_user_1', JSON.stringify([{...sofa, quantity: 1}]))
    const cancelPayment = vi.fn(() => ({cancelled: true}))
    mockStore({
      '/me/': {id: 1, username: 'shopper'},
      '/profile/': {email: 'luna@example.com'},
      '/addresses/': [{id: 1, full_name: 'Luna Shopper', city: 'Mumbai', address: '10 Test Street', phone: '9876543210', postal_code: '400001', is_default: true}],
      '/payments/razorpay/config/': {enabled: true},
      '/payments/razorpay/create-order/': {order_id: 10, razorpay_order_id: 'order_test'},
      '/payments/razorpay/cancel/': cancelPayment,
    })
    vi.stubGlobal('Razorpay', class {
      constructor(options) { this.options=options }
      on(event, handler) { if (event==='payment.failed') this.onFailure=handler }
      open() {
        if (method==='razorpay_emi') {
          expect(this.options.config.display.blocks.emi.instruments).toEqual([{method:'emi'}])
          expect(this.options.config.display.preferences.show_default_blocks).toBe(false)
        }
        this.onFailure()
        this.options.modal.ondismiss()
      }
    })
    render(<App/>)
    fireEvent.click(await screen.findByRole('button', {name: 'Shopping bag: 1 items'}))
    await screen.findByDisplayValue('10 Test Street')
    fireEvent.change(screen.getByLabelText('Payment method'), {target: {value: method}})
    fireEvent.submit(screen.getByRole('button', {name: buttonLabel}).closest('form'))

    expect(await screen.findByText(`${failure}. Your order was not placed. You can try again from your bag.`)).toBeInTheDocument()
    expect(cancelPayment).toHaveBeenCalledOnce()
    expect(screen.getByRole('button', {name: 'Shopping bag: 1 items'})).toBeInTheDocument()
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

  it('offers enlargement for one photo and shows confirmed alternate photos when available', () => {
    const {rerender} = render(<ProductColourPreview product={product} photo={product.image_url}/>)
    expect(screen.getByRole('button', {name: 'Enlarge photo'})).toBeInTheDocument()
    expect(screen.queryByText(/360°/)).toBeNull()

    const side = {image:'/media/luna-side.jpg',alt_text:'Side view'}
    rerender(<ProductColourPreview product={{...product, images:[side]}} photo={product.image_url}/>)
    expect(screen.getByRole('button', {name: 'View product photos'})).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', {name: 'Show product photo 2'}))
    expect(screen.getByAltText(product.name)).toHaveAttribute('src', side.image)
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
  it('shows only the code and applies it when clicked', () => {
    const onApply = vi.fn()
    render(<CartCouponOffers
      coupons={[{ code: 'HOME10', discount_type: 'percent', discount_value: 10, minimum_order: 5000, description: 'Furniture offer' }]}
      selectedCode=""
      onApply={onApply}
    />)

    expect(screen.queryByText('Furniture offer')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'HOME10' }))
    expect(onApply).toHaveBeenCalledWith('HOME10')
  })
})
